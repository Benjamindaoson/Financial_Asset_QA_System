"""
Multimodal Chart Fusion for GraphRAG.

This module provides multimodal fusion capabilities for chart understanding,
combining visual, textual, and structural information for enhanced chart analysis.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from PIL import Image
import cv2

logger = logging.getLogger(__name__)


class MultimodalFusion(nn.Module):
    """Multimodal fusion network for chart understanding."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize multimodal fusion network.

        Args:
            config: Fusion configuration
        """
        super(MultimodalFusion, self).__init__()

        self.config = config or {}

        # Feature dimensions
        self.visual_dim = self.config.get('visual_dim', 512)
        self.text_dim = self.config.get('text_dim', 768)
        self.structural_dim = self.config.get('structural_dim', 256)
        self.fusion_dim = self.config.get('fusion_dim', 512)

        # Modality encoders
        self.visual_encoder = self._build_visual_encoder()
        self.text_encoder = self._build_text_encoder()
        self.structural_encoder = self._build_structural_encoder()

        # Fusion layers
        self.fusion_method = self.config.get('fusion_method', 'attention')
        self.fusion_network = self._build_fusion_network()

        # Output projection
        self.output_proj = nn.Linear(self.fusion_dim, self.fusion_dim)

        # Attention mechanism
        if self.fusion_method == 'attention':
            self.attention = nn.MultiheadAttention(self.fusion_dim, num_heads=8)

    def _build_visual_encoder(self) -> nn.Module:
        """Build visual feature encoder."""
        return nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(256, self.visual_dim)
        )

    def _build_text_encoder(self) -> nn.Module:
        """Build text feature encoder."""
        return nn.Sequential(
            nn.Linear(self.text_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, self.text_dim)
        )

    def _build_structural_encoder(self) -> nn.Module:
        """Build structural feature encoder."""
        return nn.Sequential(
            nn.Linear(self.structural_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, self.structural_dim)
        )

    def _build_fusion_network(self) -> nn.Module:
        """Build fusion network based on method."""
        if self.fusion_method == 'concat':
            return nn.Sequential(
                nn.Linear(self.visual_dim + self.text_dim + self.structural_dim, self.fusion_dim),
                nn.ReLU(),
                nn.Dropout(0.1)
            )
        elif self.fusion_method == 'attention':
            return nn.Sequential(
                nn.Linear(self.visual_dim + self.text_dim + self.structural_dim, self.fusion_dim),
                nn.ReLU(),
                nn.Dropout(0.1)
            )
        elif self.fusion_method == 'cross_modal':
            return CrossModalFusion(self.visual_dim, self.text_dim, self.structural_dim, self.fusion_dim)
        else:
            raise ValueError(f"Unknown fusion method: {self.fusion_method}")

    def forward(self, visual_features: torch.Tensor,
                text_features: torch.Tensor,
                structural_features: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for multimodal fusion.

        Args:
            visual_features: Visual features (batch_size, visual_dim)
            text_features: Text features (batch_size, text_dim)
            structural_features: Structural features (batch_size, structural_dim)

        Returns:
            Fused features (batch_size, fusion_dim)
        """
        # Encode each modality
        visual_encoded = self.visual_encoder(visual_features) if len(visual_features.shape) > 2 else visual_features
        text_encoded = self.text_encoder(text_features)
        structural_encoded = self.structural_encoder(structural_features)

        # Concatenate features
        if self.fusion_method == 'concat':
            combined = torch.cat([visual_encoded, text_encoded, structural_encoded], dim=-1)
            fused = self.fusion_network(combined)

        elif self.fusion_method == 'attention':
            combined = torch.cat([visual_encoded, text_encoded, structural_encoded], dim=-1)
            fused = self.fusion_network(combined)

            # Apply attention
            fused = fused.unsqueeze(0)  # Add sequence dimension
            attended, _ = self.attention(fused, fused, fused)
            fused = attended.squeeze(0)

        elif self.fusion_method == 'cross_modal':
            fused = self.fusion_network(visual_encoded, text_encoded, structural_encoded)

        # Output projection
        output = self.output_proj(fused)

        return output


class CrossModalFusion(nn.Module):
    """Cross-modal attention fusion network."""

    def __init__(self, visual_dim: int, text_dim: int, structural_dim: int, fusion_dim: int):
        super(CrossModalFusion, self).__init__()

        self.visual_dim = visual_dim
        self.text_dim = text_dim
        self.structural_dim = structural_dim
        self.fusion_dim = fusion_dim

        # Cross-modal attention layers
        self.visual_to_text = nn.MultiheadAttention(text_dim, num_heads=4)
        self.text_to_visual = nn.MultiheadAttention(visual_dim, num_heads=4)
        self.visual_to_structural = nn.MultiheadAttention(structural_dim, num_heads=4)
        self.structural_to_visual = nn.MultiheadAttention(visual_dim, num_heads=4)
        self.text_to_structural = nn.MultiheadAttention(structural_dim, num_heads=4)
        self.structural_to_text = nn.MultiheadAttention(text_dim, num_heads=4)

        # Fusion projection
        self.fusion_proj = nn.Linear(visual_dim + text_dim + structural_dim, fusion_dim)

    def forward(self, visual: torch.Tensor, text: torch.Tensor, structural: torch.Tensor) -> torch.Tensor:
        """Cross-modal attention fusion."""
        # Add sequence dimension for attention
        visual_seq = visual.unsqueeze(0)
        text_seq = text.unsqueeze(0)
        structural_seq = structural.unsqueeze(0)

        # Cross-modal attention
        # Visual -> Text
        visual_to_text, _ = self.visual_to_text(
            visual_seq, text_seq, text_seq
        )

        # Text -> Visual
        text_to_visual, _ = self.text_to_visual(
            text_seq, visual_seq, visual_seq
        )

        # Visual -> Structural
        visual_to_structural, _ = self.visual_to_structural(
            visual_seq, structural_seq, structural_seq
        )

        # Structural -> Visual
        structural_to_visual, _ = self.structural_to_visual(
            structural_seq, visual_seq, visual_seq
        )

        # Text -> Structural
        text_to_structural, _ = self.text_to_structural(
            text_seq, structural_seq, structural_seq
        )

        # Structural -> Text
        structural_to_text, _ = self.structural_to_text(
            structural_seq, text_seq, text_seq
        )

        # Remove sequence dimension
        visual_fused = (visual_to_text + text_to_visual + visual_to_structural + structural_to_visual).squeeze(0)
        text_fused = (text_to_visual + visual_to_text + text_to_structural + structural_to_text).squeeze(0)
        structural_fused = (structural_to_visual + visual_to_structural + structural_to_text + text_to_structural).squeeze(0)

        # Concatenate and project
        combined = torch.cat([visual_fused, text_fused, structural_fused], dim=-1)
        fused = self.fusion_proj(combined)

        return fused


class MultimodalChartFusion:
    """
    Multimodal fusion system for chart understanding.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize multimodal chart fusion.

        Args:
            config: Fusion configuration
        """
        self.config = config or {}

        # Feature extractors
        self.visual_extractor = None
        self.text_extractor = None
        self.structural_extractor = None

        # Fusion model
        self.fusion_model = MultimodalFusion(self.config)

        # Device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.fusion_model.to(self.device)

        # Feature dimensions
        self.visual_dim = self.config.get('visual_dim', 512)
        self.text_dim = self.config.get('text_dim', 768)
        self.structural_dim = self.config.get('structural_dim', 256)

        logger.info("Multimodal Chart Fusion initialized")

    def fuse_chart_modalities(self, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fuse multimodal information from chart.

        Args:
            chart_data: Chart data with multiple modalities

        Returns:
            Fused chart representation
        """
        try:
            # Extract features from each modality
            visual_features = self._extract_visual_features(chart_data)
            text_features = self._extract_text_features(chart_data)
            structural_features = self._extract_structural_features(chart_data)

            # Convert to tensors
            visual_tensor = torch.tensor(visual_features, dtype=torch.float32).to(self.device)
            text_tensor = torch.tensor(text_features, dtype=torch.float32).to(self.device)
            structural_tensor = torch.tensor(structural_features, dtype=torch.float32).to(self.device)

            # Perform fusion
            self.fusion_model.eval()
            with torch.no_grad():
                fused_features = self.fusion_model(visual_tensor, text_tensor, structural_tensor)

            # Convert back to numpy
            fused_features = fused_features.cpu().numpy()

            return {
                'fused_features': fused_features.tolist(),
                'feature_dim': len(fused_features),
                'modalities_used': {
                    'visual': visual_features is not None,
                    'text': text_features is not None,
                    'structural': structural_features is not None
                },
                'fusion_method': self.config.get('fusion_method', 'attention'),
                'success': True
            }

        except Exception as e:
            logger.error(f"Multimodal fusion failed: {e}")
            return {
                'error': str(e),
                'success': False
            }

    def _extract_visual_features(self, chart_data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Extract visual features from chart image."""
        image = chart_data.get('image')
        if image is None:
            return None

        try:
            # Convert to tensor if needed
            if isinstance(image, Image.Image):
                image = np.array(image)
            elif isinstance(image, np.ndarray):
                pass
            else:
                return None

            # Convert to RGB if needed
            if len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)

            # Resize for model input
            image = cv2.resize(image, (224, 224))

            # Convert to tensor and normalize
            image_tensor = torch.tensor(image, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
            image_tensor = image_tensor / 255.0  # Normalize to [0, 1]

            # Extract features using the visual encoder
            with torch.no_grad():
                features = self.fusion_model.visual_encoder(image_tensor.to(self.device))
                features = features.cpu().numpy().flatten()

            return features

        except Exception as e:
            logger.warning(f"Visual feature extraction failed: {e}")
            return None

    def _extract_text_features(self, chart_data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Extract text features from chart."""
        texts = chart_data.get('extracted_texts', [])
        if not texts:
            return None

        try:
            # Combine all text
            combined_text = ' '.join(texts) if texts else ''

            if not combined_text.strip():
                return np.zeros(self.text_dim, dtype=np.float32)

            # Simple text embedding (would use proper text encoder in production)
            # For now, create a basic embedding based on text length and content
            text_length = len(combined_text)
            word_count = len(combined_text.split())
            char_diversity = len(set(combined_text.lower())) / max(1, len(combined_text))

            # Create feature vector
            features = np.array([
                min(text_length / 1000, 1.0),  # Normalized text length
                min(word_count / 100, 1.0),    # Normalized word count
                char_diversity,                  # Character diversity
                1.0 if any(char.isdigit() for char in combined_text) else 0.0,  # Has numbers
                1.0 if any(char in '.,!?;:()[]{}' for char in combined_text) else 0.0,  # Has punctuation
            ], dtype=np.float32)

            # Pad or truncate to text_dim
            if len(features) < self.text_dim:
                features = np.pad(features, (0, self.text_dim - len(features)))
            else:
                features = features[:self.text_dim]

            return features

        except Exception as e:
            logger.warning(f"Text feature extraction failed: {e}")
            return np.zeros(self.text_dim, dtype=np.float32)

    def _extract_structural_features(self, chart_data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Extract structural features from chart."""
        elements = chart_data.get('chart_elements', {})
        if not elements:
            return None

        try:
            features = []

            # Count different element types
            element_counts = {}
            for element_type in ['data_points', 'axes', 'labels', 'legend', 'title']:
                count = len(elements.get(element_type, []))
                element_counts[element_type] = count
                features.append(min(count / 50, 1.0))  # Normalize

            # Layout features
            if 'data_regions' in elements:
                regions = elements['data_regions']
                if regions:
                    # Calculate layout density
                    total_area = sum((r['bbox'][2] - r['bbox'][0]) * (r['bbox'][3] - r['bbox'][1])
                                   for r in regions)
                    features.append(min(total_area / 100000, 1.0))  # Normalized area

            # Chart type indicators (one-hot style)
            chart_type = chart_data.get('chart_type', '')
            chart_types = ['bar', 'line', 'pie', 'scatter', 'histogram', 'area']
            type_features = [1.0 if chart_type.lower().startswith(ct) else 0.0 for ct in chart_types]
            features.extend(type_features)

            # Complexity features
            total_elements = sum(element_counts.values())
            features.append(min(total_elements / 100, 1.0))  # Overall complexity

            # Convert to numpy array
            features = np.array(features, dtype=np.float32)

            # Pad or truncate to structural_dim
            if len(features) < self.structural_dim:
                features = np.pad(features, (0, self.structural_dim - len(features)))
            else:
                features = features[:self.structural_dim]

            return features

        except Exception as e:
            logger.warning(f"Structural feature extraction failed: {e}")
            return np.zeros(self.structural_dim, dtype=np.float32)

    def batch_fusion(self, chart_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform fusion on a batch of charts.

        Args:
            chart_batch: List of chart data

        Returns:
            List of fusion results
        """
        results = []

        for chart_data in chart_batch:
            result = self.fuse_chart_modalities(chart_data)
            results.append(result)

        return results

    def get_fusion_info(self) -> Dict[str, Any]:
        """Get fusion system information."""
        return {
            'fusion_method': self.config.get('fusion_method', 'attention'),
            'visual_dim': self.visual_dim,
            'text_dim': self.text_dim,
            'structural_dim': self.structural_dim,
            'fusion_dim': self.config.get('fusion_dim', 512),
            'device': str(self.device),
            'config': self.config
        }

    def update_fusion_weights(self, feedback_data: Dict[str, Any]):
        """
        Update fusion model based on feedback.

        Args:
            feedback_data: Feedback for model improvement
        """
        # This would implement online learning or fine-tuning
        # For now, just log the feedback
        logger.info(f"Received fusion feedback: {feedback_data}")

    def evaluate_fusion_quality(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate fusion quality on test data.

        Args:
            test_data: Test chart data with ground truth

        Returns:
            Quality metrics
        """
        # Placeholder for fusion quality evaluation
        return {
            'fusion_accuracy': 0.85,  # Placeholder
            'modality_contribution': {
                'visual': 0.4,
                'text': 0.3,
                'structural': 0.3
            },
            'evaluation_samples': len(test_data)
        }







