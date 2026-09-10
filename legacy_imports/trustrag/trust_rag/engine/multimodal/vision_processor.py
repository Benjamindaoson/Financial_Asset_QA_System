"""
Vision Processor for GraphRAG.

This module provides vision-language processing capabilities using
ViT (Vision Transformer) and multimodal models for image understanding.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from PIL import Image
import torch
import torch.nn as nn
from transformers import ViTImageProcessor, ViTModel, CLIPProcessor, CLIPModel
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class VisionProcessor:
    """
    Vision processor using ViT and multimodal models.

    Provides image understanding, feature extraction, and multimodal embeddings
    for charts, diagrams, and visual content in documents.
    """

    def __init__(
        self,
        model_name: str = "google/vit-base-patch16-224",
        clip_model_name: str = "openai/clip-vit-base-patch32",
        device: str = "auto"
    ):
        """
        Initialize vision processor.

        Args:
            model_name: ViT model name
            clip_model_name: CLIP model name for multimodal embeddings
            device: Device to run models on ('auto', 'cpu', 'cuda')
        """
        self.device = self._setup_device(device)

        # Initialize ViT model for feature extraction
        self.vit_processor = ViTImageProcessor.from_pretrained(model_name)
        self.vit_model = ViTModel.from_pretrained(model_name).to(self.device)
        self.vit_model.eval()

        # Initialize CLIP model for multimodal embeddings
        self.clip_processor = CLIPProcessor.from_pretrained(clip_model_name)
        self.clip_model = CLIPModel.from_pretrained(clip_model_name).to(self.device)
        self.clip_model.eval()

        logger.info(f"Vision processor initialized with device: {self.device}")

    def _setup_device(self, device: str) -> str:
        """Setup compute device."""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def extract_image_features(self, image: Union[str, Path, Image.Image]) -> np.ndarray:
        """
        Extract features from image using ViT.

        Args:
            image: Image path or PIL Image

        Returns:
            Feature vector as numpy array
        """
        try:
            # Load and preprocess image
            if isinstance(image, (str, Path)):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            # Process with ViT
            inputs = self.vit_processor(pil_image, return_tensors="pt").to(self.device)

            with torch.no_grad():
                outputs = self.vit_model(**inputs)
                # Use CLS token features (first token)
                features = outputs.last_hidden_state[:, 0, :].cpu().numpy()

            return features.flatten()

        except Exception as e:
            logger.error(f"Failed to extract image features: {e}")
            return np.array([])

    def get_multimodal_embedding(self, image: Union[str, Path, Image.Image], text: str = "") -> np.ndarray:
        """
        Get multimodal embedding combining image and text.

        Args:
            image: Image path or PIL Image
            text: Optional text description

        Returns:
            Multimodal embedding vector
        """
        try:
            # Load image
            if isinstance(image, (str, Path)):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            # Process with CLIP
            inputs = self.clip_processor(
                text=[text] if text else [""],
                images=pil_image,
                return_tensors="pt",
                padding=True
            ).to(self.device)

            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                # Use multimodal embedding (average of text and image features)
                image_features = outputs.image_embeds
                text_features = outputs.text_embeds

                if text:
                    # Combine text and image features
                    multimodal_features = (image_features + text_features) / 2
                else:
                    multimodal_features = image_features

            return multimodal_features.cpu().numpy().flatten()

        except Exception as e:
            logger.error(f"Failed to get multimodal embedding: {e}")
            return np.array([])

    def analyze_image_content(self, image: Union[str, Path, Image.Image]) -> Dict[str, Any]:
        """
        Analyze image content and extract structured information.

        Args:
            image: Image path or PIL Image

        Returns:
            Dictionary with analysis results
        """
        try:
            # Load image
            if isinstance(image, (str, Path)):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            analysis = {
                "dimensions": pil_image.size,
                "mode": pil_image.mode,
                "features_extracted": False,
                "multimodal_embedding_available": False,
                "content_type": self._classify_image_type(pil_image)
            }

            # Extract features
            features = self.extract_image_features(pil_image)
            if len(features) > 0:
                analysis["features_extracted"] = True
                analysis["feature_dim"] = len(features)

            # Get multimodal embedding
            embedding = self.get_multimodal_embedding(pil_image)
            if len(embedding) > 0:
                analysis["multimodal_embedding_available"] = True
                analysis["embedding_dim"] = len(embedding)

            # Additional analysis based on content type
            if analysis["content_type"] == "chart":
                analysis.update(self._analyze_chart_content(pil_image))
            elif analysis["content_type"] == "table":
                analysis.update(self._analyze_table_content(pil_image))
            elif analysis["content_type"] == "diagram":
                analysis.update(self._analyze_diagram_content(pil_image))

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze image content: {e}")
            return {"error": str(e)}

    def _classify_image_type(self, image: Image.Image) -> str:
        """
        Classify image content type using simple heuristics.

        Args:
            image: PIL Image

        Returns:
            Content type classification
        """
        width, height = image.size

        # Convert to numpy array for analysis
        img_array = np.array(image)

        # Simple heuristics for classification
        # Check for chart-like patterns (lines, colors)
        if self._has_chart_patterns(img_array):
            return "chart"
        elif self._has_table_patterns(img_array):
            return "table"
        elif self._has_diagram_patterns(img_array):
            return "diagram"
        else:
            return "general"

    def _has_chart_patterns(self, img_array: np.ndarray) -> bool:
        """Check for chart-like patterns in image."""
        # Simple heuristic: look for lines and color variations
        # This is a simplified implementation
        try:
            # Check for horizontal/vertical lines
            gray = np.mean(img_array, axis=2) if len(img_array.shape) == 3 else img_array
            edges = np.abs(np.diff(gray, axis=0)) + np.abs(np.diff(gray, axis=1))
            line_score = np.mean(edges > 50)  # Threshold for line detection

            # Check for color diversity (charts often have multiple colors)
            if len(img_array.shape) == 3:
                unique_colors = len(np.unique(img_array.reshape(-1, 3), axis=0))
                color_score = unique_colors / (img_array.shape[0] * img_array.shape[1])
            else:
                color_score = 0

            return line_score > 0.1 or color_score > 0.01

        except:
            return False

    def _has_table_patterns(self, img_array: np.ndarray) -> bool:
        """Check for table-like patterns in image."""
        try:
            # Look for grid-like patterns
            gray = np.mean(img_array, axis=2) if len(img_array.shape) == 3 else img_array

            # Check for regular horizontal and vertical lines
            h_lines = np.mean(np.abs(np.diff(gray, axis=0)), axis=1)
            v_lines = np.mean(np.abs(np.diff(gray, axis=1)), axis=0)

            h_score = np.sum(h_lines > 30) / len(h_lines)
            v_score = np.sum(v_lines > 30) / len(v_lines)

            return h_score > 0.1 and v_score > 0.1

        except:
            return False

    def _has_diagram_patterns(self, img_array: np.ndarray) -> bool:
        """Check for diagram-like patterns in image."""
        try:
            # Look for shapes and connections
            gray = np.mean(img_array, axis=2) if len(img_array.shape) == 3 else img_array

            # Edge detection
            edges = np.abs(np.diff(gray, axis=0)) + np.abs(np.diff(gray, axis=1))
            edge_density = np.mean(edges > 20)

            return edge_density > 0.05

        except:
            return False

    def _analyze_chart_content(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze chart-specific content."""
        return {
            "chart_type": "detected",
            "axes_detected": True,  # Simplified
            "data_points": "estimated",
            "legend_present": False  # Simplified
        }

    def _analyze_table_content(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze table-specific content."""
        return {
            "rows_detected": "estimated",
            "columns_detected": "estimated",
            "headers_present": True  # Simplified
        }

    def _analyze_diagram_content(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze diagram-specific content."""
        return {
            "shapes_detected": "estimated",
            "connections_found": "estimated",
            "flow_direction": "detected"  # Simplified
        }

    def batch_process_images(self, image_paths: List[Union[str, Path]]) -> List[Dict[str, Any]]:
        """
        Process multiple images in batch.

        Args:
            image_paths: List of image paths

        Returns:
            List of analysis results
        """
        results = []

        for path in image_paths:
            try:
                analysis = self.analyze_image_content(path)
                analysis["image_path"] = str(path)
                results.append(analysis)
            except Exception as e:
                logger.error(f"Failed to process image {path}: {e}")
                results.append({
                    "image_path": str(path),
                    "error": str(e)
                })

        return results







