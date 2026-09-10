"""
GNN Engine for GraphRAG.

This module provides Graph Neural Network capabilities for
relevance assessment, graph-based reasoning, and knowledge discovery.
"""

from .relevance_scorer import RelevanceScorer
from .graph_reasoner import GraphReasoner
from .gnn_model import GNNModel
from .graph_embedder import GraphEmbedder

__all__ = [
    'RelevanceScorer',
    'GraphReasoner',
    'GNNModel',
    'GraphEmbedder'
]







