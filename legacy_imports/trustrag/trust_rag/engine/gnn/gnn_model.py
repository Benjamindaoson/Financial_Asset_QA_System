"""
GNN Model for GraphRAG.

This module implements Graph Neural Network models for relevance assessment
and graph-based reasoning in the knowledge graph.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv
from torch_geometric.data import Data
import numpy as np

logger = logging.getLogger(__name__)


class GNNModel(nn.Module):
    """
    Graph Neural Network model for GraphRAG.

    Supports multiple GNN architectures (GCN, GAT, GraphSAGE) for
    node classification, link prediction, and graph-level tasks.
    """

    def __init__(
        self,
        node_dim: int = 1024,  # BGE-M3 dimension
        hidden_dim: int = 256,
        output_dim: int = 1024, # Match query dimension for cosine sim
        num_layers: int = 3,
        model_type: str = "gcn",
        num_heads: int = 8,
        dropout: float = 0.1,
        activation: str = "relu"
    ):
        """
        Initialize GNN model.

        Args:
            node_dim: Input node feature dimension
            hidden_dim: Hidden layer dimension
            output_dim: Output dimension
            num_layers: Number of GNN layers
            model_type: Type of GNN ('gcn', 'gat', 'sage')
            num_heads: Number of attention heads (for GAT)
            dropout: Dropout rate
            activation: Activation function
        """
        super().__init__()

        self.node_dim = node_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        self.model_type = model_type
        self.num_heads = num_heads
        self.dropout = dropout

        # Activation function
        if activation == "relu":
            self.activation = F.relu
        elif activation == "gelu":
            self.activation = F.gelu
        else:
            self.activation = F.elu

        # Input projection
        self.input_proj = nn.Linear(node_dim, hidden_dim)

        # GNN layers
        self.gnn_layers = nn.ModuleList()
        for i in range(num_layers):
            in_dim = hidden_dim if i > 0 else hidden_dim
            out_dim = hidden_dim

            if model_type == "gcn":
                self.gnn_layers.append(GCNConv(in_dim, out_dim))
            elif model_type == "gat":
                self.gnn_layers.append(GATConv(in_dim, out_dim // num_heads, heads=num_heads))
            elif model_type == "sage":
                self.gnn_layers.append(SAGEConv(in_dim, out_dim))
            else:
                raise ValueError(f"Unknown GNN type: {model_type}")

        # Output projection
        gnn_out_dim = hidden_dim
        if model_type == "gat":
            gnn_out_dim = hidden_dim  # GAT already handles head concatenation

        self.output_proj = nn.Linear(gnn_out_dim, output_dim)

        # Layer normalization
        self.layer_norms = nn.ModuleList([
            nn.LayerNorm(hidden_dim) for _ in range(num_layers)
        ])

        logger.info(f"Initialized {model_type.upper()} model: {node_dim}->{hidden_dim}->{output_dim}")

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through GNN.

        Args:
            x: Node features [num_nodes, node_dim]
            edge_index: Edge indices [2, num_edges]

        Returns:
            Node embeddings [num_nodes, output_dim]
        """
        # Input projection
        x = self.input_proj(x)
        x = self.activation(x)

        # GNN layers
        for i, layer in enumerate(self.gnn_layers):
            x = layer(x, edge_index)
            x = self.layer_norms[i](x)
            x = self.activation(x)
            x = F.dropout(x, p=self.dropout, training=self.training)

        # Output projection
        x = self.output_proj(x)
        return x

    def predict_relevance(
        self,
        query_emb: torch.Tensor,
        node_embs: torch.Tensor
    ) -> torch.Tensor:
        """
        Predict relevance scores between query and nodes.

        Args:
            query_emb: Query embedding [query_dim]
            node_embs: Node embeddings [num_nodes, node_dim]

        Returns:
            Relevance scores [num_nodes]
        """
        if query_emb.dim() == 1:
            query_emb = query_emb.unsqueeze(0)  # [1, query_dim]

        # Use Cosine Similarity for robust zero-shot relevance
        # Projecting with random definition is worse than direct comparison
        
        # Ensure dimensions match (if not, we might need a fixed projection, but valid config avoids this)
        if query_emb.shape[-1] != node_embs.shape[-1]:
             # Fallback: Pad or slice (simple hack for now if mismatch occurs)
             mdim = min(query_emb.shape[-1], node_embs.shape[-1])
             query_emb = query_emb[..., :mdim]
             node_embs = node_embs[..., :mdim]

        # Normalize
        query_norm = F.normalize(query_emb, p=2, dim=-1)
        node_norm = F.normalize(node_embs, p=2, dim=-1)
        
        # Cosine similarity
        similarities = torch.matmul(node_norm, query_norm.transpose(-2, -1)).squeeze(-1)

        # Map -1..1 to 0..1 for probability
        relevance_scores = (similarities + 1) / 2

        return relevance_scores.squeeze()

    def predict_links(
        self,
        node_embs: torch.Tensor,
        edge_candidates: torch.Tensor
    ) -> torch.Tensor:
        """
        Predict link existence between node pairs.

        Args:
            node_embs: Node embeddings [num_nodes, emb_dim]
            edge_candidates: Candidate edges [num_candidates, 2]

        Returns:
            Link prediction scores [num_candidates]
        """
        # Get embeddings for candidate node pairs
        src_embs = node_embs[edge_candidates[:, 0]]  # [num_candidates, emb_dim]
        dst_embs = node_embs[edge_candidates[:, 1]]  # [num_candidates, emb_dim]

        # Concatenate and predict
        link_features = torch.cat([src_embs, dst_embs], dim=-1)  # [num_candidates, 2*emb_dim]

        # Simple MLP for link prediction
        link_predictor = nn.Sequential(
            nn.Linear(2 * node_embs.shape[-1], node_embs.shape[-1]),
            nn.ReLU(),
            nn.Linear(node_embs.shape[-1], 1),
            nn.Sigmoid()
        ).to(node_embs.device)

        link_scores = link_predictor(link_features).squeeze(-1)

        return link_scores


class MultiModalGNN(nn.Module):
    """
    Multi-modal GNN that combines text, vision, and graph information.
    """

    def __init__(
        self,
        text_dim: int = 768,
        vision_dim: int = 768,
        graph_dim: int = 256,
        hidden_dim: int = 512,
        output_dim: int = 256
    ):
        """
        Initialize multi-modal GNN.

        Args:
            text_dim: Text embedding dimension
            vision_dim: Vision embedding dimension
            graph_dim: Graph node embedding dimension
            hidden_dim: Hidden dimension
            output_dim: Output dimension
        """
        super().__init__()

        # Modality-specific encoders
        self.text_encoder = nn.Sequential(
            nn.Linear(text_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

        self.vision_encoder = nn.Sequential(
            nn.Linear(vision_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

        # Graph GNN
        self.graph_gnn = GNNModel(
            node_dim=output_dim,
            hidden_dim=hidden_dim,
            output_dim=output_dim,
            num_layers=2
        )

        # Cross-modal attention
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=output_dim,
            num_heads=8,
            batch_first=True
        )

        # Fusion layer
        self.fusion = nn.Sequential(
            nn.Linear(output_dim * 3, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

        logger.info("Initialized MultiModalGNN")

    def forward(
        self,
        text_emb: Optional[torch.Tensor] = None,
        vision_emb: Optional[torch.Tensor] = None,
        graph_x: Optional[torch.Tensor] = None,
        graph_edge_index: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass for multi-modal fusion.

        Args:
            text_emb: Text embeddings [batch_size, seq_len, text_dim] or [batch_size, text_dim]
            vision_emb: Vision embeddings [batch_size, vision_dim]
            graph_x: Graph node features [num_nodes, graph_dim]
            graph_edge_index: Graph edges [2, num_edges]

        Returns:
            Dictionary with fused representations
        """
        outputs = {}

        # Encode modalities
        if text_emb is not None:
            if text_emb.dim() == 3:
                # Mean pool sequence dimension
                text_emb = text_emb.mean(dim=1)
            outputs['text_encoded'] = self.text_encoder(text_emb)

        if vision_emb is not None:
            outputs['vision_encoded'] = self.vision_encoder(vision_emb)

        if graph_x is not None and graph_edge_index is not None:
            outputs['graph_encoded'] = self.graph_gnn(graph_x, graph_edge_index)

        # Cross-modal fusion if multiple modalities available
        available_modalities = [k for k in outputs.keys() if k.endswith('_encoded')]

        if len(available_modalities) > 1:
            # Stack available modality embeddings
            modality_embs = torch.stack([outputs[k] for k in available_modalities], dim=0)

            # Cross-attention
            attended, _ = self.cross_attention(modality_embs, modality_embs, modality_embs)

            # Concatenate and fuse
            concat_embs = torch.cat([outputs[k] for k in available_modalities], dim=-1)
            outputs['fused'] = self.fusion(concat_embs)
        elif len(available_modalities) == 1:
            # Single modality
            outputs['fused'] = outputs[available_modalities[0]]

        return outputs


class RelevanceScorer:
    """
    Relevance scorer using GNN for query-document matching.
    """

    def __init__(self, gnn_model: Optional[GNNModel] = None):
        """
        Initialize relevance scorer.

        Args:
            gnn_model: Pre-trained GNN model
        """
        self.gnn_model = gnn_model or GNNModel()
        self.device = next(self.gnn_model.parameters()).device

    def score_relevance(
        self,
        query_emb: np.ndarray,
        doc_embs: np.ndarray,
        graph_data: Optional[Data] = None
    ) -> np.ndarray:
        """
        Score relevance between query and documents using GNN.

        Args:
            query_emb: Query embedding
            doc_embs: Document embeddings
            graph_data: Optional graph structure data

        Returns:
            Relevance scores
        """
        try:
            # Convert to tensors
            query_tensor = torch.tensor(query_emb, dtype=torch.float32).to(self.device)
            doc_tensor = torch.tensor(doc_embs, dtype=torch.float32).to(self.device)

            if graph_data:
                # Use graph structure for scoring
                graph_data = graph_data.to(self.device)
                node_embs = self.gnn_model(graph_data.x, graph_data.edge_index)
                scores = self.gnn_model.predict_relevance(query_tensor, node_embs)
            else:
                # Direct relevance prediction
                scores = self.gnn_model.predict_relevance(query_tensor, doc_tensor)

            return scores.cpu().numpy()

        except Exception as e:
            logger.error(f"GNN relevance scoring failed: {e}")
            # Fallback to cosine similarity
            return np.array([
                np.dot(query_emb, doc_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(doc_emb))
                for doc_emb in doc_embs
            ])

    def update_model(self, training_data: List[Dict[str, Any]]) -> None:
        """
        Update GNN model with new training data.

        Args:
            training_data: Training examples with queries, documents, and relevance labels
        """
        # Placeholder for model fine-tuning
        logger.info(f"Would fine-tune GNN model with {len(training_data)} examples")
        # In practice, this would implement the training loop







