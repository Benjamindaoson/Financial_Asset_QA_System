"""
GNN Chart Reasoner for GraphRAG.

This module provides graph neural network-based reasoning for chart data,
enabling complex relationship analysis and inference over chart-derived graphs.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv
from torch_geometric.data import Data, Batch
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class ChartGraphData:
    """Data structure for chart-derived graphs."""

    def __init__(self, nodes: List[Dict[str, Any]], edges: List[Tuple[int, int, Dict[str, Any]]]):
        """
        Initialize chart graph data.

        Args:
            nodes: List of node dictionaries with features
            edges: List of (source, target, attributes) tuples
        """
        self.nodes = nodes
        self.edges = edges

        # Build adjacency information
        self.node_map = {node['id']: i for i, node in enumerate(nodes)}
        self.node_features = []
        self.edge_index = []
        self.edge_attr = []

        self._process_nodes()
        self._process_edges()

    def _process_nodes(self):
        """Process node features."""
        for node in self.nodes:
            # Extract or create node features
            features = self._extract_node_features(node)
            self.node_features.append(features)

    def _process_edges(self):
        """Process edge information."""
        for source, target, attrs in self.edges:
            if source in self.node_map and target in self.node_map:
                src_idx = self.node_map[source]
                tgt_idx = self.node_map[target]

                self.edge_index.extend([[src_idx, tgt_idx], [tgt_idx, src_idx]])  # Bidirectional

                # Edge features
                edge_features = self._extract_edge_features(attrs)
                self.edge_attr.extend([edge_features, edge_features])  # Bidirectional

    def _extract_node_features(self, node: Dict[str, Any]) -> np.ndarray:
        """Extract features from chart node."""
        features = []

        # Node type encoding (one-hot)
        node_types = ['data_point', 'axis', 'label', 'legend', 'title', 'grid']
        type_encoding = [1.0 if node.get('type') == t else 0.0 for t in node_types]
        features.extend(type_encoding)

        # Position features
        bbox = node.get('bbox', [0, 0, 0, 0])
        features.extend([
            bbox[0], bbox[1],  # x, y
            bbox[2] - bbox[0],  # width
            bbox[3] - bbox[1],  # height
            (bbox[2] + bbox[0]) / 2,  # center x
            (bbox[3] + bbox[1]) / 2   # center y
        ])

        # Value features (if applicable)
        if 'value' in node:
            features.append(float(node['value']))
        else:
            features.append(0.0)

        # Text length (if applicable)
        if 'text' in node:
            features.append(len(node['text']))
        else:
            features.append(0.0)

        return np.array(features, dtype=np.float32)

    def _extract_edge_features(self, attrs: Dict[str, Any]) -> np.ndarray:
        """Extract features from chart edge."""
        features = []

        # Relationship type encoding
        rel_types = ['contains', 'adjacent', 'connects', 'labels', 'belongs_to']
        type_encoding = [1.0 if attrs.get('type') == t else 0.0 for t in rel_types]
        features.extend(type_encoding)

        # Distance feature (if positions available)
        distance = attrs.get('distance', 0.0)
        features.append(distance)

        # Directional features
        features.extend([
            attrs.get('horizontal_distance', 0.0),
            attrs.get('vertical_distance', 0.0)
        ])

        return np.array(features, dtype=np.float32)

    def to_pyg_data(self) -> Data:
        """Convert to PyTorch Geometric Data object."""
        x = torch.tensor(np.array(self.node_features), dtype=torch.float)
        edge_index = torch.tensor(self.edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(np.array(self.edge_attr), dtype=torch.float) if self.edge_attr else None

        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)


class ChartGNN(nn.Module):
    """Graph Neural Network for chart reasoning."""

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, num_layers: int = 3,
                 gnn_type: str = 'gcn'):
        """
        Initialize Chart GNN.

        Args:
            input_dim: Input feature dimension
            hidden_dim: Hidden layer dimension
            output_dim: Output dimension
            num_layers: Number of GNN layers
            gnn_type: Type of GNN ('gcn', 'gat', 'sage')
        """
        super(ChartGNN, self).__init__()

        self.gnn_type = gnn_type
        self.num_layers = num_layers

        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)

        # GNN layers
        self.convs = nn.ModuleList()
        for i in range(num_layers):
            in_dim = hidden_dim
            out_dim = hidden_dim

            if gnn_type == 'gcn':
                self.convs.append(GCNConv(in_dim, out_dim))
            elif gnn_type == 'gat':
                self.convs.append(GATConv(in_dim, out_dim // 4, heads=4, concat=True))
            elif gnn_type == 'sage':
                self.convs.append(SAGEConv(in_dim, out_dim))
            else:
                raise ValueError(f"Unknown GNN type: {gnn_type}")

        # Output layers
        self.output_proj = nn.Linear(hidden_dim, output_dim)

        # Batch normalization
        self.bns = nn.ModuleList([nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)])

        # Dropout
        self.dropout = nn.Dropout(0.5)

    def forward(self, data: Data) -> torch.Tensor:
        """Forward pass."""
        x, edge_index, edge_attr = data.x, data.edge_index, data.edge_attr

        # Input projection
        x = self.input_proj(x)
        x = F.relu(x)

        # GNN layers
        for i, conv in enumerate(self.convs):
            if self.gnn_type == 'gat':
                x = conv(x, edge_index)
            else:
                x = conv(x, edge_index)

            x = self.bns[i](x)
            x = F.relu(x)
            x = self.dropout(x)

        # Output projection
        x = self.output_proj(x)

        return x


class GNNChartReasoner:
    """
    GNN-based reasoning system for chart understanding and analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize GNN chart reasoner.

        Args:
            config: Reasoning configuration
        """
        self.config = config or {}

        # Model configuration
        self.input_dim = self.config.get('input_dim', 16)  # Node feature dimension
        self.hidden_dim = self.config.get('hidden_dim', 64)
        self.output_dim = self.config.get('output_dim', 32)
        self.num_layers = self.config.get('num_layers', 3)
        self.gnn_type = self.config.get('gnn_type', 'gcn')

        # Reasoning tasks
        self.tasks = {
            'relationship_prediction': self._predict_relationships,
            'anomaly_detection': self._detect_anomalies,
            'trend_analysis': self._analyze_trends,
            'pattern_recognition': self._recognize_patterns,
            'data_completion': self._complete_missing_data
        }

        # Initialize models
        self.models = {}
        self._init_models()

        # Device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.to_device()

        logger.info(f"GNN Chart Reasoner initialized with {self.gnn_type} model")

    def _init_models(self):
        """Initialize GNN models for different tasks."""
        for task_name in self.tasks.keys():
            model = ChartGNN(
                input_dim=self.input_dim,
                hidden_dim=self.hidden_dim,
                output_dim=self.output_dim,
                num_layers=self.num_layers,
                gnn_type=self.gnn_type
            )
            self.models[task_name] = model

    def to_device(self):
        """Move models to device."""
        for model in self.models.values():
            model.to(self.device)

    def reason_over_chart(self, chart_graph: ChartGraphData, task: str = 'relationship_prediction') -> Dict[str, Any]:
        """
        Perform reasoning over chart graph.

        Args:
            chart_graph: Chart graph data
            task: Reasoning task to perform

        Returns:
            Reasoning results
        """
        if task not in self.tasks:
            raise ValueError(f"Unknown reasoning task: {task}")

        try:
            # Convert to PyG data
            pyg_data = chart_graph.to_pyg_data()
            pyg_data = pyg_data.to(self.device)

            # Get appropriate model
            model = self.models[task]
            model.eval()

            # Perform reasoning
            with torch.no_grad():
                output = model(pyg_data)

            # Process results
            result_processor = self.tasks[task]
            results = result_processor(output, chart_graph)

            return {
                'task': task,
                'results': results,
                'node_count': len(chart_graph.nodes),
                'edge_count': len(chart_graph.edges),
                'success': True
            }

        except Exception as e:
            logger.error(f"GNN reasoning failed: {e}")
            return {
                'task': task,
                'error': str(e),
                'success': False
            }

    def _predict_relationships(self, output: torch.Tensor, chart_graph: ChartGraphData) -> Dict[str, Any]:
        """Predict relationships between chart elements."""
        # Analyze node embeddings to find relationships
        node_embeddings = output.cpu().numpy()

        relationships = []

        # Find similar nodes (potential relationships)
        from sklearn.metrics.pairwise import cosine_similarity
        similarity_matrix = cosine_similarity(node_embeddings)

        # Extract high-confidence relationships
        for i in range(len(node_embeddings)):
            for j in range(i + 1, len(node_embeddings)):
                if similarity_matrix[i, j] > 0.8:  # High similarity threshold
                    relationships.append({
                        'source_node': chart_graph.nodes[i]['id'],
                        'target_node': chart_graph.nodes[j]['id'],
                        'relationship_type': 'similar',
                        'confidence': float(similarity_matrix[i, j])
                    })

        return {
            'predicted_relationships': relationships,
            'total_relationships': len(relationships)
        }

    def _detect_anomalies(self, output: torch.Tensor, chart_graph: ChartGraphData) -> Dict[str, Any]:
        """Detect anomalies in chart data."""
        node_embeddings = output.cpu().numpy()

        # Calculate reconstruction error or use clustering
        from sklearn.cluster import DBSCAN
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        normalized_embeddings = scaler.fit_transform(node_embeddings)

        # DBSCAN for anomaly detection
        clustering = DBSCAN(eps=0.5, min_samples=2)
        labels = clustering.fit_predict(normalized_embeddings)

        # Nodes with label -1 are anomalies
        anomalies = []
        for i, label in enumerate(labels):
            if label == -1:
                anomalies.append({
                    'node_id': chart_graph.nodes[i]['id'],
                    'node_type': chart_graph.nodes[i].get('type'),
                    'anomaly_score': 1.0  # Simplified score
                })

        return {
            'detected_anomalies': anomalies,
            'anomaly_count': len(anomalies),
            'total_nodes': len(chart_graph.nodes)
        }

    def _analyze_trends(self, output: torch.Tensor, chart_graph: ChartGraphData) -> Dict[str, Any]:
        """Analyze trends in chart data."""
        # Look for temporal or sequential patterns
        trends = []

        # Find data point nodes
        data_points = [node for node in chart_graph.nodes if node.get('type') == 'data_point']

        if len(data_points) > 2:
            # Sort by position (assuming left-to-right layout)
            data_points.sort(key=lambda x: x.get('bbox', [0, 0, 0, 0])[0])

            # Analyze value trends
            values = []
            for point in data_points:
                value = point.get('value', 0)
                if isinstance(value, (int, float)):
                    values.append(value)

            if len(values) > 1:
                # Calculate trend direction
                diffs = np.diff(values)
                increasing_count = sum(1 for d in diffs if d > 0)
                decreasing_count = sum(1 for d in diffs if d < 0)

                if increasing_count > decreasing_count:
                    trend = 'increasing'
                elif decreasing_count > increasing_count:
                    trend = 'decreasing'
                else:
                    trend = 'stable'

                trends.append({
                    'trend_type': 'value_trend',
                    'direction': trend,
                    'data_points': len(values),
                    'confidence': min(0.9, abs(increasing_count - decreasing_count) / len(diffs))
                })

        return {
            'detected_trends': trends,
            'trend_count': len(trends)
        }

    def _recognize_patterns(self, output: torch.Tensor, chart_graph: ChartGraphData) -> Dict[str, Any]:
        """Recognize patterns in chart structure."""
        patterns = []

        # Analyze graph structure for common patterns
        node_types = [node.get('type') for node in chart_graph.nodes]
        type_counts = defaultdict(int)

        for node_type in node_types:
            type_counts[node_type] += 1

        # Detect chart type patterns
        if type_counts.get('data_point', 0) > 10:
            if self._has_grid_pattern(chart_graph):
                patterns.append({
                    'pattern_type': 'grid_layout',
                    'description': 'Regular grid pattern typical of scatter plots or heatmaps',
                    'confidence': 0.8
                })

        if self._has_axis_pattern(chart_graph):
            patterns.append({
                'pattern_type': 'axis_based',
                'description': 'Axis-based layout typical of line/bar charts',
                'confidence': 0.9
            })

        return {
            'recognized_patterns': patterns,
            'pattern_count': len(patterns)
        }

    def _complete_missing_data(self, output: torch.Tensor, chart_graph: ChartGraphData) -> Dict[str, Any]:
        """Complete missing data points using graph patterns."""
        completions = []

        # Find nodes with missing values
        for node in chart_graph.nodes:
            if node.get('type') == 'data_point' and node.get('value') is None:
                # Use neighboring nodes to estimate value
                neighbors = self._find_neighbors(node, chart_graph)

                if neighbors:
                    neighbor_values = [n.get('value') for n in neighbors if n.get('value') is not None]
                    if neighbor_values:
                        estimated_value = np.mean(neighbor_values)
                        completions.append({
                            'node_id': node['id'],
                            'estimated_value': estimated_value,
                            'method': 'neighbor_average',
                            'neighbor_count': len(neighbor_values)
                        })

        return {
            'data_completions': completions,
            'completion_count': len(completions)
        }

    def _has_grid_pattern(self, chart_graph: ChartGraphData) -> bool:
        """Check if chart has a grid-like pattern."""
        # Simplified grid detection
        positions = []
        for node in chart_graph.nodes:
            if node.get('type') == 'data_point':
                bbox = node.get('bbox', [0, 0, 0, 0])
                positions.append((bbox[0], bbox[1]))  # x, y

        if len(positions) < 9:  # Need at least 3x3 grid
            return False

        # Check for regular spacing
        x_coords = sorted(set(pos[0] for pos in positions))
        y_coords = sorted(set(pos[1] for pos in positions))

        # Check if coordinates are regularly spaced
        x_diffs = np.diff(x_coords)
        y_diffs = np.diff(y_coords)

        x_variance = np.var(x_diffs) if len(x_diffs) > 0 else float('inf')
        y_variance = np.var(y_diffs) if len(y_diffs) > 0 else float('inf')

        # Low variance indicates regular spacing
        return x_variance < 1000 and y_variance < 1000

    def _has_axis_pattern(self, chart_graph: ChartGraphData) -> bool:
        """Check if chart has axis-based layout."""
        has_x_axis = any(node.get('type') == 'axis' and
                        node.get('orientation') == 'horizontal'
                        for node in chart_graph.nodes)
        has_y_axis = any(node.get('type') == 'axis' and
                        node.get('orientation') == 'vertical'
                        for node in chart_graph.nodes)

        return has_x_axis or has_y_axis

    def _find_neighbors(self, node: Dict[str, Any], chart_graph: ChartGraphData) -> List[Dict[str, Any]]:
        """Find neighboring nodes."""
        neighbors = []
        node_bbox = node.get('bbox', [0, 0, 0, 0])

        for other_node in chart_graph.nodes:
            if other_node['id'] != node['id']:
                other_bbox = other_node.get('bbox', [0, 0, 0, 0])

                # Check if bounding boxes are adjacent
                if self._bboxes_adjacent(node_bbox, other_bbox):
                    neighbors.append(other_node)

        return neighbors

    def _bboxes_adjacent(self, bbox1: List[float], bbox2: List[float]) -> bool:
        """Check if two bounding boxes are adjacent."""
        # Simple adjacency check
        x1, y1, x2, y2 = bbox1
        x3, y3, x4, y4 = bbox2

        # Check horizontal adjacency
        horizontal_adjacent = (abs(x2 - x3) < 10 and max(y1, y3) < min(y2, y4)) or \
                             (abs(x4 - x1) < 10 and max(y1, y3) < min(y2, y4))

        # Check vertical adjacency
        vertical_adjacent = (abs(y2 - y3) < 10 and max(x1, x3) < min(x2, x4)) or \
                           (abs(y4 - y1) < 10 and max(x1, x3) < min(x2, x4))

        return horizontal_adjacent or vertical_adjacent

    def batch_reason(self, chart_graphs: List[ChartGraphData], task: str = 'relationship_prediction') -> List[Dict[str, Any]]:
        """
        Perform reasoning on multiple charts in batch.

        Args:
            chart_graphs: List of chart graphs
            task: Reasoning task

        Returns:
            List of reasoning results
        """
        results = []

        for chart_graph in chart_graphs:
            result = self.reason_over_chart(chart_graph, task)
            results.append(result)

        return results

    def get_reasoner_info(self) -> Dict[str, Any]:
        """Get reasoner information."""
        return {
            'gnn_type': self.gnn_type,
            'input_dim': self.input_dim,
            'hidden_dim': self.hidden_dim,
            'output_dim': self.output_dim,
            'num_layers': self.num_layers,
            'available_tasks': list(self.tasks.keys()),
            'device': str(self.device),
            'config': self.config
        }







