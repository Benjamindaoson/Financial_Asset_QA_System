"""
Multimodal Fusion for GraphRAG.

This module provides multimodal data fusion capabilities, combining
text, image, table, and chart data into unified representations
for graph-based reasoning and retrieval.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from collections import defaultdict

from .vision_processor import VisionProcessor
from .table_parser import TableParser

logger = logging.getLogger(__name__)


class MultimodalFusion(nn.Module):
    """
    Multimodal fusion model combining text, vision, and tabular data.

    Uses attention mechanisms and cross-modal transformers to create
    unified representations for knowledge graph construction.
    """

    def __init__(
        self,
        text_dim: int = 768,
        vision_dim: int = 768,
        table_dim: int = 256,
        fusion_dim: int = 512,
        num_heads: int = 8,
        num_layers: int = 3
    ):
        """
        Initialize multimodal fusion model.

        Args:
            text_dim: Text embedding dimension
            vision_dim: Vision embedding dimension
            table_dim: Table data dimension
            fusion_dim: Fused representation dimension
            num_heads: Number of attention heads
            num_layers: Number of fusion layers
        """
        super().__init__()

        self.text_dim = text_dim
        self.vision_dim = vision_dim
        self.table_dim = table_dim
        self.fusion_dim = fusion_dim

        # Projection layers to align different modalities
        self.text_projection = nn.Linear(text_dim, fusion_dim)
        self.vision_projection = nn.Linear(vision_dim, fusion_dim)
        self.table_projection = nn.Linear(table_dim, fusion_dim)

        # Cross-modal attention layers
        self.cross_attention_layers = nn.ModuleList([
            nn.MultiheadAttention(fusion_dim, num_heads, batch_first=True)
            for _ in range(num_layers)
        ])

        # Fusion layer
        self.fusion_layer = nn.Sequential(
            nn.Linear(fusion_dim * 3, fusion_dim),
            nn.LayerNorm(fusion_dim),
            nn.ReLU(),
            nn.Linear(fusion_dim, fusion_dim)
        )

        # Modality weights (learnable)
        self.modality_weights = nn.Parameter(torch.ones(3))  # text, vision, table

        # Layer norm for stability
        self.layer_norm = nn.LayerNorm(fusion_dim)

        logger.info(f"Multimodal fusion model initialized with fusion_dim={fusion_dim}")

    def forward(
        self,
        text_emb: Optional[torch.Tensor] = None,
        vision_emb: Optional[torch.Tensor] = None,
        table_emb: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass for multimodal fusion.

        Args:
            text_emb: Text embeddings [batch_size, seq_len, text_dim]
            vision_emb: Vision embeddings [batch_size, vision_dim]
            table_emb: Table embeddings [batch_size, table_dim]

        Returns:
            Fused multimodal representation [batch_size, fusion_dim]
        """
        # Project to common dimension
        projected_embs = []

        if text_emb is not None:
            # Use mean pooling for text sequences
            if text_emb.dim() == 3:
                text_emb = text_emb.mean(dim=1)  # [batch_size, text_dim]
            text_proj = self.text_projection(text_emb)  # [batch_size, fusion_dim]
            projected_embs.append(text_proj)

        if vision_emb is not None:
            vision_proj = self.vision_projection(vision_emb)  # [batch_size, fusion_dim]
            projected_embs.append(vision_proj)

        if table_emb is not None:
            table_proj = self.table_projection(table_emb)  # [batch_size, fusion_dim]
            projected_embs.append(table_proj)

        if not projected_embs:
            # Return zero tensor if no inputs
            return torch.zeros(1, self.fusion_dim, device=self.text_projection.weight.device)

        # Stack available modalities
        modality_stack = torch.stack(projected_embs, dim=0)  # [num_modalities, batch_size, fusion_dim]

        # Apply cross-modal attention
        attended_features = modality_stack
        for attention_layer in self.cross_attention_layers:
            # Self-attention within modalities, cross-attention between modalities
            attended_features, _ = attention_layer(
                attended_features, attended_features, attended_features
            )

        # Weighted fusion
        weights = torch.softmax(self.modality_weights[:len(projected_embs)], dim=0)
        weights = weights.view(-1, 1, 1)  # [num_modalities, 1, 1]

        fused = torch.sum(attended_features * weights, dim=0)  # [batch_size, fusion_dim]

        # Final fusion layer
        fused = self.fusion_layer(torch.cat([
            text_proj if 'text_proj' in locals() else torch.zeros_like(fused),
            vision_proj if 'vision_proj' in locals() else torch.zeros_like(fused),
            table_proj if 'table_proj' in locals() else torch.zeros_like(fused)
        ], dim=-1))

        return self.layer_norm(fused)


class MultimodalProcessor:
    """
    High-level multimodal processor coordinating vision, text, and table processing.
    """

    def __init__(
        self,
        vision_processor: Optional[VisionProcessor] = None,
        table_parser: Optional[TableParser] = None,
        device: str = "auto"
    ):
        """
        Initialize multimodal processor.

        Args:
            vision_processor: Vision processor instance
            table_parser: Table parser instance
            device: Compute device
        """
        self.vision_processor = vision_processor or VisionProcessor(device=device)
        self.table_parser = table_parser or TableParser()

        # Initialize fusion model
        self.fusion_model = MultimodalFusion()
        self.device = device

        # Feature scaler for normalization
        self.scaler = StandardScaler()

        logger.info("Multimodal processor initialized")

    def process_document_content(
        self,
        text_content: str,
        image_paths: List[str] = None,
        table_data: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process multimodal document content.

        Args:
            text_content: Text content of document
            image_paths: Paths to images in document
            table_data: Pre-extracted table data

        Returns:
            Multimodal processing results
        """
        results = {
            "text_analysis": {},
            "image_analysis": [],
            "table_analysis": [],
            "multimodal_fusion": {},
            "graph_entities": []
        }

        try:
            # Process text content
            results["text_analysis"] = self._analyze_text_content(text_content)

            # Process images
            if image_paths:
                results["image_analysis"] = self.vision_processor.batch_process_images(image_paths)

            # Process tables
            if table_data:
                results["table_analysis"] = [
                    self.table_parser.convert_table_to_graph_format(table)
                    for table in table_data
                ]

            # Multimodal fusion
            results["multimodal_fusion"] = self._fuse_multimodal_data(
                results["text_analysis"],
                results["image_analysis"],
                results["table_analysis"]
            )

            # Extract graph entities
            results["graph_entities"] = self._extract_graph_entities(results)

        except Exception as e:
            logger.error(f"Failed to process multimodal content: {e}")
            results["error"] = str(e)

        return results

    def _analyze_text_content(self, text: str) -> Dict[str, Any]:
        """Analyze text content for entities and structure."""
        # Simple text analysis - would integrate with NLP models
        analysis = {
            "length": len(text),
            "sentences": len(text.split('.')),
            "words": len(text.split()),
            "entities": self._extract_text_entities(text),
            "key_phrases": self._extract_key_phrases(text),
            "structure": self._analyze_text_structure(text)
        }

        return analysis

    def _extract_text_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text."""
        entities = []

        # Simple entity extraction patterns (would use NER model)
        import re

        # Company patterns
        companies = re.findall(r'\b[A-Z][a-zA-Z\s&]+(?:Inc|Corp|LLC| Ltd| PLC)\b', text)
        for company in companies:
            entities.append({
                "text": company,
                "type": "company",
                "start": text.find(company),
                "end": text.find(company) + len(company)
            })

        # Financial metrics
        metrics = re.findall(r'\b(?:revenue|profit|income|earnings|sales|margin)\b', text, re.IGNORECASE)
        for metric in metrics:
            entities.append({
                "text": metric,
                "type": "metric",
                "start": text.find(metric),
                "end": text.find(metric) + len(metric)
            })

        return entities

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text."""
        # Simple key phrase extraction (would use NLP models)
        phrases = []

        # Extract noun phrases (simplified)
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        phrases.extend(words[:10])  # Limit to top phrases

        return list(set(phrases))

    def _analyze_text_structure(self, text: str) -> Dict[str, Any]:
        """Analyze text structure."""
        return {
            "has_sections": "Section" in text or "##" in text,
            "has_lists": "-" in text or "*" in text,
            "has_tables": "Table" in text.lower(),
            "has_figures": "Figure" in text or "Fig." in text
        }

    def _fuse_multimodal_data(
        self,
        text_analysis: Dict[str, Any],
        image_analysis: List[Dict[str, Any]],
        table_analysis: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fuse multimodal data into unified representation."""
        fusion_result = {
            "modality_count": 0,
            "fusion_score": 0.0,
            "cross_references": [],
            "unified_entities": []
        }

        # Count available modalities
        modalities = []
        if text_analysis.get("entities"):
            modalities.append("text")
        if image_analysis:
            modalities.append("vision")
        if table_analysis:
            modalities.append("table")

        fusion_result["modality_count"] = len(modalities)
        fusion_result["available_modalities"] = modalities

        # Calculate fusion score based on consistency
        fusion_result["fusion_score"] = self._calculate_fusion_score(
            text_analysis, image_analysis, table_analysis
        )

        # Find cross-references between modalities
        fusion_result["cross_references"] = self._find_cross_references(
            text_analysis, image_analysis, table_analysis
        )

        # Create unified entity representations
        fusion_result["unified_entities"] = self._create_unified_entities(
            text_analysis, image_analysis, table_analysis
        )

        return fusion_result

    def _calculate_fusion_score(
        self,
        text_analysis: Dict[str, Any],
        image_analysis: List[Dict[str, Any]],
        table_analysis: List[Dict[str, Any]]
    ) -> float:
        """Calculate multimodal fusion consistency score."""
        score = 0.0
        factors = 0

        # Text-vision consistency
        if text_analysis.get("entities") and image_analysis:
            # Check if entities mentioned in text appear in image analysis
            text_entities = {e["text"].lower() for e in text_analysis["entities"]}
            image_texts = set()
            for img in image_analysis:
                # Would check OCR results or captions
                pass

            factors += 1

        # Text-table consistency
        if text_analysis.get("entities") and table_analysis:
            # Check if entities appear in table headers/data
            factors += 1

        # Vision-table consistency
        if image_analysis and table_analysis:
            # Check for chart-table relationships
            chart_images = [img for img in image_analysis if img.get("content_type") == "chart"]
            if chart_images and table_analysis:
                score += 0.3  # Charts often correspond to tables
            factors += 1

        return min(score / max(factors, 1), 1.0)

    def _find_cross_references(
        self,
        text_analysis: Dict[str, Any],
        image_analysis: List[Dict[str, Any]],
        table_analysis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find cross-references between modalities."""
        references = []

        # Text to image references
        for entity in text_analysis.get("entities", []):
            entity_text = entity["text"].lower()
            for img in image_analysis:
                # Would check for mentions in image context
                if "mentions" in str(img).lower() and entity_text in str(img).lower():
                    references.append({
                        "type": "text_to_image",
                        "text_entity": entity["text"],
                        "image_path": img.get("image_path"),
                        "confidence": 0.8
                    })

        # Text to table references
        for entity in text_analysis.get("entities", []):
            entity_text = entity["text"].lower()
            for table in table_analysis:
                table_text = str(table).lower()
                if entity_text in table_text:
                    references.append({
                        "type": "text_to_table",
                        "text_entity": entity["text"],
                        "table_id": table.get("table_node", {}).get("id"),
                        "confidence": 0.9
                    })

        # Image to table references (charts to data tables)
        chart_images = [img for img in image_analysis if img.get("content_type") == "chart"]
        for chart in chart_images:
            for table in table_analysis:
                # Would check for chart-table correspondence
                references.append({
                    "type": "chart_to_table",
                    "chart_path": chart.get("image_path"),
                    "table_id": table.get("table_node", {}).get("id"),
                    "confidence": 0.7
                })

        return references

    def _create_unified_entities(
        self,
        text_analysis: Dict[str, Any],
        image_analysis: List[Dict[str, Any]],
        table_analysis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create unified entity representations across modalities."""
        unified_entities = []

        # Collect entities from all modalities
        entity_sources = defaultdict(list)

        # From text
        for entity in text_analysis.get("entities", []):
            entity_sources[entity["text"]].append({
                "source": "text",
                "type": entity["type"],
                "confidence": 0.8
            })

        # From tables
        for table in table_analysis:
            for cell in table.get("cell_nodes", []):
                if cell.get("properties", {}).get("is_metric"):
                    value = cell["properties"]["value"]
                    entity_sources[value].append({
                        "source": "table",
                        "type": "metric",
                        "table_id": cell["properties"]["table_id"],
                        "confidence": 0.9
                    })

        # From images (would need OCR results)
        for img in image_analysis:
            # Placeholder for OCR-extracted entities
            pass

        # Create unified representations
        for entity_text, sources in entity_sources.items():
            # Determine primary type
            type_counts = defaultdict(int)
            for source in sources:
                type_counts[source["type"]] += 1

            primary_type = max(type_counts, key=type_counts.get)

            # Calculate confidence based on source agreement
            avg_confidence = sum(s["confidence"] for s in sources) / len(sources)
            agreement_bonus = 0.1 if len(set(s["type"] for s in sources)) == 1 else 0

            unified_entity = {
                "text": entity_text,
                "type": primary_type,
                "confidence": min(avg_confidence + agreement_bonus, 1.0),
                "sources": sources,
                "modality_count": len(sources)
            }

            unified_entities.append(unified_entity)

        return unified_entities

    def _extract_graph_entities(self, processing_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities suitable for graph construction."""
        entities = []

        # From unified entities
        for entity in processing_results.get("multimodal_fusion", {}).get("unified_entities", []):
            graph_entity = {
                "id": f"entity_{hash(entity['text']) % 1000000}",
                "type": "entity",
                "label": entity["text"],
                "properties": {
                    "entity_type": entity["type"],
                    "confidence": entity["confidence"],
                    "modality_sources": [s["source"] for s in entity["sources"]],
                    "text": entity["text"]
                }
            }
            entities.append(graph_entity)

        # From table structures
        for table in processing_results.get("table_analysis", []):
            # Add table as entity
            if "table_node" in table:
                table_node = table["table_node"]
                entities.append({
                    "id": table_node["id"],
                    "type": "table",
                    "label": f"Table: {table_node['id']}",
                    "properties": table_node["properties"]
                })

            # Add metrics as entities
            for cell in table.get("cell_nodes", []):
                if cell.get("properties", {}).get("is_metric"):
                    entities.append({
                        "id": cell["id"],
                        "type": "metric",
                        "label": cell["properties"]["value"],
                        "properties": cell["properties"]
                    })

        # From image analysis
        for img in processing_results.get("image_analysis", []):
            if img.get("content_type") in ["chart", "diagram"]:
                entities.append({
                    "id": f"visual_{hash(img.get('image_path', '')) % 1000000}",
                    "type": "visual",
                    "label": f"{img.get('content_type', 'visual').title()}: {img.get('image_path', '')}",
                    "properties": {
                        "content_type": img.get("content_type"),
                        "image_path": img.get("image_path"),
                        "analysis": img
                    }
                })

        return entities







