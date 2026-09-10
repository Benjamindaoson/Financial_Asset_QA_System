"""
Chart to Graph Converter for GraphRAG.

This module converts chart data and analysis results into knowledge graph
structures with nodes, edges, and relationships for graph-based reasoning.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import uuid

from ...graph_db.graph_types import Node, Edge, KnowledgeGraph, NodeType, EdgeType

logger = logging.getLogger(__name__)


class ChartToGraphConverter:
    """
    Convert chart analysis results to knowledge graph structures.

    Creates nodes for chart elements, data points, and relationships
    that capture the chart's semantic meaning and data relationships.
    """

    def __init__(self):
        """Initialize chart to graph converter."""
        self.node_id_counter = 0
        self.edge_id_counter = 0

    def convert_to_graph(self, chart_analysis: Dict[str, Any],
                        data_extraction: Dict[str, Any],
                        chart_metadata: Dict[str, Any] = None) -> KnowledgeGraph:
        """
        Convert chart analysis and data to knowledge graph.

        Args:
            chart_analysis: Results from ChartParser
            data_extraction: Results from ChartDataExtractor
            chart_metadata: Additional metadata about the chart

        Returns:
            Knowledge graph representing the chart
        """
        graph = KnowledgeGraph()
        chart_metadata = chart_metadata or {}

        try:
            # Create main chart node
            chart_node = self._create_chart_node(chart_analysis, chart_metadata)
            graph.add_node(chart_node)

            # Create nodes for chart elements
            element_nodes = self._create_element_nodes(chart_analysis, chart_node.id)
            for node in element_nodes:
                graph.add_node(node)

            # Create data nodes
            data_nodes = self._create_data_nodes(data_extraction, chart_node.id)
            for node in data_nodes:
                graph.add_node(node)

            # Create relationship edges
            relationship_edges = self._create_relationship_edges(
                chart_node, element_nodes, data_nodes, chart_analysis, data_extraction
            )
            for edge in relationship_edges:
                graph.add_edge(edge)

            # Create semantic edges (data relationships)
            semantic_edges = self._create_semantic_edges(data_nodes, chart_analysis)
            for edge in semantic_edges:
                graph.add_edge(edge)

            logger.info(f"Converted chart to graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")

        except Exception as e:
            logger.error(f"Failed to convert chart to graph: {e}")

        return graph

    def _create_chart_node(self, chart_analysis: Dict[str, Any],
                          chart_metadata: Dict[str, Any]) -> Node:
        """Create the main chart node."""
        chart_id = f"chart_{uuid.uuid4().hex[:8]}"

        classification = chart_analysis.get('classification', {})
        chart_type = classification.get('chart_type', 'unknown')
        confidence = classification.get('confidence', 0.0)

        chart_node = Node(
            id=chart_id,
            type=NodeType.CHART,
            label=f"{chart_type.replace('_', ' ').title()} Chart",
            properties={
                'chart_type': chart_type,
                'confidence': confidence,
                'description': classification.get('description', ''),
                'title': chart_metadata.get('title', ''),
                'source': chart_metadata.get('source', 'unknown'),
                'creation_date': chart_metadata.get('creation_date'),
                'dimensions': chart_metadata.get('dimensions')
            },
            metadata={
                'parsing_metadata': chart_analysis.get('metadata', {}),
                'extraction_confidence': chart_metadata.get('extraction_confidence', 0.0)
            }
        )

        return chart_node

    def _create_element_nodes(self, chart_analysis: Dict[str, Any], chart_id: str) -> List[Node]:
        """Create nodes for chart elements (axes, legend, etc.)."""
        nodes = []
        elements = chart_analysis.get('elements', {})

        # Create axis nodes
        axes = elements.get('axes', {})
        if axes.get('x_axis'):
            x_axis_node = Node(
                id=f"x_axis_{chart_id}",
                type=NodeType.CONCEPT,
                label="X-Axis",
                properties={
                    'axis_type': 'x',
                    'orientation': axes['x_axis'].get('orientation', 'horizontal'),
                    'start_point': axes['x_axis'].get('start'),
                    'end_point': axes['x_axis'].get('end'),
                    'chart_id': chart_id
                }
            )
            nodes.append(x_axis_node)

        if axes.get('y_axis'):
            y_axis_node = Node(
                id=f"y_axis_{chart_id}",
                type=NodeType.CONCEPT,
                label="Y-Axis",
                properties={
                    'axis_type': 'y',
                    'orientation': axes['y_axis'].get('orientation', 'vertical'),
                    'start_point': axes['y_axis'].get('start'),
                    'end_point': axes['y_axis'].get('end'),
                    'chart_id': chart_id
                }
            )
            nodes.append(y_axis_node)

        # Create legend node
        legend = elements.get('legend')
        if legend:
            legend_node = Node(
                id=f"legend_{chart_id}",
                type=NodeType.CONCEPT,
                label="Chart Legend",
                properties={
                    'position': legend.get('position', 'unknown'),
                    'bbox': legend.get('bbox'),
                    'items': legend.get('items', []),
                    'chart_id': chart_id
                }
            )
            nodes.append(legend_node)

        # Create data region nodes
        data_regions = elements.get('data_regions', [])
        for i, region in enumerate(data_regions):
            region_node = Node(
                id=f"data_region_{chart_id}_{i}",
                type=NodeType.CONCEPT,
                label=f"Data Region {i+1}",
                properties={
                    'region_type': region.get('type', 'unknown'),
                    'bbox': region.get('bbox'),
                    'confidence': region.get('confidence', 0.0),
                    'chart_id': chart_id
                }
            )
            nodes.append(region_node)

        return nodes

    def _create_data_nodes(self, data_extraction: Dict[str, Any], chart_id: str) -> List[Node]:
        """Create nodes for extracted data points and series."""
        nodes = []
        final_data = data_extraction.get('final_data', [])

        for data_item in final_data:
            data_type = data_item.get('type', 'unknown')

            if data_type == 'bar_data':
                # Create data point node for bar
                data_node = Node(
                    id=f"data_point_{chart_id}_{data_item.get('index', 0)}",
                    type=NodeType.METRIC,
                    label=f"Bar {data_item.get('index', 0) + 1}: {data_item.get('value', 0)}",
                    properties={
                        'value': data_item.get('value', 0),
                        'label': data_item.get('label', ''),
                        'position': data_item.get('position'),
                        'dimensions': data_item.get('dimensions'),
                        'chart_id': chart_id,
                        'data_type': 'bar_value'
                    }
                )
                nodes.append(data_node)

            elif data_type == 'pie_segment':
                # Create segment node for pie chart
                data_node = Node(
                    id=f"pie_segment_{chart_id}_{data_item.get('index', 0)}",
                    type=NodeType.METRIC,
                    label=f"{data_item.get('label', '')}: {data_item.get('percentage', 0):.1f}%",
                    properties={
                        'value': data_item.get('value', 0),
                        'percentage': data_item.get('percentage', 0),
                        'angle': data_item.get('metadata', {}).get('angle', 0),
                        'color': data_item.get('color'),
                        'label': data_item.get('label', ''),
                        'chart_id': chart_id,
                        'data_type': 'pie_segment'
                    }
                )
                nodes.append(data_node)

            elif data_type == 'chart_summary':
                # Create summary node for complex charts
                summary_node = Node(
                    id=f"chart_summary_{chart_id}",
                    type=NodeType.CONCEPT,
                    label="Chart Data Summary",
                    properties={
                        'data_points': data_item.get('data_points', 0),
                        'text_elements': data_item.get('text_elements', 0),
                        'chart_type': data_item.get('chart_type', 'unknown'),
                        'confidence': data_item.get('metadata', {}).get('confidence', 0.0),
                        'chart_id': chart_id
                    }
                )
                nodes.append(summary_node)

        # Create series nodes for multi-series data
        series_nodes = self._create_series_nodes(data_extraction, chart_id)
        nodes.extend(series_nodes)

        return nodes

    def _create_series_nodes(self, data_extraction: Dict[str, Any], chart_id: str) -> List[Node]:
        """Create nodes for data series in charts."""
        nodes = []
        chart_data = data_extraction.get('chart_data', {})

        # Handle line chart series
        series_list = chart_data.get('series', [])
        for series in series_list:
            series_node = Node(
                id=f"series_{chart_id}_{series.get('index', 0)}",
                type=NodeType.CONCEPT,
                label=f"Data Series {series.get('index', 0) + 1}",
                properties={
                    'series_index': series.get('index', 0),
                    'point_count': len(series.get('points', [])),
                    'trend': series.get('trend', 'unknown'),
                    'chart_id': chart_id,
                    'series_type': 'line_series'
                }
            )
            nodes.append(series_node)

        return nodes

    def _create_relationship_edges(self, chart_node: Node,
                                 element_nodes: List[Node],
                                 data_nodes: List[Node],
                                 chart_analysis: Dict[str, Any],
                                 data_extraction: Dict[str, Any]) -> List[Edge]:
        """Create relationship edges between nodes."""
        edges = []

        # Chart to element relationships
        for element_node in element_nodes:
            if 'axis' in element_node.id:
                edge_type = EdgeType.CONTAINS
                relationship = 'has_axis'
            elif 'legend' in element_node.id:
                edge_type = EdgeType.CONTAINS
                relationship = 'has_legend'
            elif 'data_region' in element_node.id:
                edge_type = EdgeType.CONTAINS
                relationship = 'has_data_region'
            else:
                edge_type = EdgeType.CONTAINS
                relationship = 'contains'

            edge = Edge(
                id=f"edge_{chart_node.id}_{element_node.id}",
                source_id=chart_node.id,
                target_id=element_node.id,
                type=edge_type,
                weight=0.9,
                properties={
                    'relationship_type': relationship,
                    'confidence': 0.9
                }
            )
            edges.append(edge)

        # Chart to data relationships
        for data_node in data_nodes:
            if 'data_point' in data_node.id or 'pie_segment' in data_node.id:
                edge_type = EdgeType.CONTAINS
                relationship = 'contains_data'
                weight = 1.0
            elif 'series' in data_node.id:
                edge_type = EdgeType.CONTAINS
                relationship = 'has_series'
                weight = 0.95
            elif 'summary' in data_node.id:
                edge_type = EdgeType.RELATED_TO
                relationship = 'summarized_by'
                weight = 0.8
            else:
                edge_type = EdgeType.CONTAINS
                relationship = 'contains'
                weight = 0.85

            edge = Edge(
                id=f"edge_{chart_node.id}_{data_node.id}",
                source_id=chart_node.id,
                target_id=data_node.id,
                type=edge_type,
                weight=weight,
                properties={
                    'relationship_type': relationship,
                    'data_type': data_node.properties.get('data_type', 'unknown')
                }
            )
            edges.append(edge)

        # Element to data relationships
        data_regions = [n for n in element_nodes if 'data_region' in n.id]
        for region_node in data_regions:
            # Connect data regions to data points within them
            region_bbox = region_node.properties.get('bbox')
            if region_bbox:
                for data_node in data_nodes:
                    if self._point_in_bbox(
                        data_node.properties.get('position', (0, 0)),
                        region_bbox
                    ):
                        edge = Edge(
                            id=f"edge_{region_node.id}_{data_node.id}",
                            source_id=region_node.id,
                            target_id=data_node.id,
                            type=EdgeType.CONTAINS,
                            weight=0.85,
                            properties={
                                'relationship_type': 'contains_data_point',
                                'spatial_relationship': True
                            }
                        )
                        edges.append(edge)

        return edges

    def _create_semantic_edges(self, data_nodes: List[Node],
                             chart_analysis: Dict[str, Any]) -> List[Edge]:
        """Create semantic edges representing data relationships."""
        edges = []
        chart_type = chart_analysis.get('classification', {}).get('chart_type', 'unknown')

        if chart_type == 'bar_chart':
            edges.extend(self._create_comparison_edges(data_nodes))
        elif chart_type == 'line_chart':
            edges.extend(self._create_trend_edges(data_nodes))
        elif chart_type == 'pie_chart':
            edges.extend(self._create_proportion_edges(data_nodes))

        # Create magnitude comparison edges for all chart types
        edges.extend(self._create_magnitude_edges(data_nodes))

        return edges

    def _create_comparison_edges(self, data_nodes: List[Node]) -> List[Edge]:
        """Create comparison edges for bar charts."""
        edges = []
        value_nodes = [n for n in data_nodes if n.properties.get('data_type') == 'bar_value']

        # Sort by value for comparison
        value_nodes.sort(key=lambda n: n.properties.get('value', 0), reverse=True)

        for i, node1 in enumerate(value_nodes):
            for j, node2 in enumerate(value_nodes):
                if i != j:
                    val1 = node1.properties.get('value', 0)
                    val2 = node2.properties.get('value', 0)

                    if val1 > val2:
                        relationship = 'higher_than'
                        weight = min((val1 - val2) / max(val1, 1), 1.0)
                    elif val1 < val2:
                        relationship = 'lower_than'
                        weight = min((val2 - val1) / max(val2, 1), 1.0)
                    else:
                        continue  # Skip equal values

                    edge = Edge(
                        id=f"comp_{node1.id}_{node2.id}",
                        source_id=node1.id,
                        target_id=node2.id,
                        type=EdgeType.RELATED_TO,
                        weight=weight,
                        properties={
                            'relationship_type': relationship,
                            'comparison_type': 'magnitude',
                            'value_difference': abs(val1 - val2)
                        }
                    )
                    edges.append(edge)

        return edges

    def _create_trend_edges(self, data_nodes: List[Node]) -> List[Edge]:
        """Create trend edges for line charts."""
        edges = []
        series_nodes = [n for n in data_nodes if 'series' in n.id]

        for series_node in series_nodes:
            trend = series_node.properties.get('trend', 'unknown')

            if trend in ['increasing', 'decreasing']:
                # Create edges between consecutive points in the series
                points = series_node.properties.get('points', [])
                for i in range(len(points) - 1):
                    point1 = points[i]
                    point2 = points[i + 1]

                    edge = Edge(
                        id=f"trend_{series_node.id}_{i}_{i+1}",
                        source_id=f"data_point_{series_node.properties['chart_id']}_{i}",
                        target_id=f"data_point_{series_node.properties['chart_id']}_{i+1}",
                        type=EdgeType.RELATED_TO,
                        weight=0.8,
                        properties={
                            'relationship_type': f'{trend}_trend',
                            'series_index': series_node.properties.get('series_index', 0),
                            'temporal_relationship': True
                        }
                    )
                    edges.append(edge)

        return edges

    def _create_proportion_edges(self, data_nodes: List[Node]) -> List[Edge]:
        """Create proportion edges for pie charts."""
        edges = []
        segment_nodes = [n for n in data_nodes if n.properties.get('data_type') == 'pie_segment']

        total_value = sum(n.properties.get('value', 0) for n in segment_nodes)

        for segment_node in segment_nodes:
            percentage = segment_node.properties.get('percentage', 0)

            # Create edges representing proportions
            for other_segment in segment_nodes:
                if segment_node.id != other_segment.id:
                    other_percentage = other_segment.properties.get('percentage', 0)

                    if percentage > other_percentage:
                        relationship = 'larger_proportion_than'
                        weight = percentage / max(other_percentage, 0.01)
                    else:
                        relationship = 'smaller_proportion_than'
                        weight = other_percentage / max(percentage, 0.01)

                    edge = Edge(
                        id=f"prop_{segment_node.id}_{other_segment.id}",
                        source_id=segment_node.id,
                        target_id=other_segment.id,
                        type=EdgeType.RELATED_TO,
                        weight=min(weight, 1.0),
                        properties={
                            'relationship_type': relationship,
                            'proportion_difference': abs(percentage - other_percentage)
                        }
                    )
                    edges.append(edge)

        return edges

    def _create_magnitude_edges(self, data_nodes: List[Node]) -> List[Edge]:
        """Create magnitude comparison edges for all data nodes."""
        edges = []
        value_nodes = []

        # Collect nodes with numeric values
        for node in data_nodes:
            if 'value' in node.properties and isinstance(node.properties['value'], (int, float)):
                value_nodes.append(node)

        # Create pairwise comparisons
        for i, node1 in enumerate(value_nodes):
            for j, node2 in enumerate(value_nodes):
                if i < j:  # Avoid duplicate comparisons
                    val1 = node1.properties['value']
                    val2 = node2.properties['value']

                    if abs(val1 - val2) / max(abs(val1), abs(val2), 1) < 0.05:
                        # Values are approximately equal
                        edge = Edge(
                            id=f"mag_equal_{node1.id}_{node2.id}",
                            source_id=node1.id,
                            target_id=node2.id,
                            type=EdgeType.SIMILAR_TO,
                            weight=0.9,
                            properties={
                                'relationship_type': 'approximately_equal',
                                'value_similarity': 1.0 - abs(val1 - val2) / max(abs(val1), abs(val2), 1)
                            }
                        )
                        edges.append(edge)

        return edges

    def _point_in_bbox(self, point: Tuple[float, float], bbox: Tuple[float, float, float, float]) -> bool:
        """Check if a point is within a bounding box."""
        px, py = point
        bx, by, bw, bh = bbox

        return bx <= px <= bx + bw and by <= py <= by + bh

    def create_domain_specific_graph(self, chart_graph: KnowledgeGraph,
                                   domain: str = 'finance') -> KnowledgeGraph:
        """
        Create domain-specific enhancements to the chart graph.

        Args:
            chart_graph: Base chart knowledge graph
            domain: Domain context (finance, healthcare, etc.)

        Returns:
            Enhanced domain-specific graph
        """
        enhanced_graph = chart_graph  # Start with base graph

        if domain == 'finance':
            enhanced_graph = self._add_financial_context(enhanced_graph)
        elif domain == 'healthcare':
            enhanced_graph = self._add_healthcare_context(enhanced_graph)

        return enhanced_graph

    def _add_financial_context(self, graph: KnowledgeGraph) -> KnowledgeGraph:
        """Add financial domain context to chart graph."""
        # Create financial concept nodes
        financial_concepts = [
            ('revenue', 'Financial revenue metric'),
            ('profit', 'Financial profit metric'),
            ('growth', 'Growth rate or trend'),
            ('margin', 'Profit margin percentage'),
            ('trend', 'Data trend over time')
        ]

        for concept_id, description in financial_concepts:
            concept_node = Node(
                id=f"finance_concept_{concept_id}",
                type=NodeType.CONCEPT,
                label=concept_id.title(),
                properties={
                    'domain': 'finance',
                    'description': description,
                    'category': 'financial_metric'
                }
            )
            graph.add_node(concept_node)

        # Link chart data to financial concepts
        for node in graph.nodes.values():
            if node.type == NodeType.METRIC:
                value = node.properties.get('value', 0)
                label = node.properties.get('label', '').lower()

                # Determine financial concept
                if any(term in label for term in ['revenue', 'sales', 'income']):
                    concept_id = 'finance_concept_revenue'
                elif any(term in label for term in ['profit', 'earnings']):
                    concept_id = 'finance_concept_profit'
                elif 'growth' in label or '%' in str(value):
                    concept_id = 'finance_concept_growth'
                else:
                    continue

                # Create relationship edge
                if concept_id in graph.nodes:
                    edge = Edge(
                        id=f"finance_link_{node.id}_{concept_id}",
                        source_id=node.id,
                        target_id=concept_id,
                        type=EdgeType.RELATED_TO,
                        weight=0.8,
                        properties={
                            'relationship_type': 'represents_financial_concept',
                            'domain_context': 'finance'
                        }
                    )
                    graph.add_edge(edge)

        return graph

    def _add_healthcare_context(self, graph: KnowledgeGraph) -> KnowledgeGraph:
        """Add healthcare domain context to chart graph."""
        # Similar to financial context but for healthcare metrics
        healthcare_concepts = [
            ('patients', 'Patient count or metrics'),
            ('treatment', 'Treatment effectiveness'),
            ('recovery', 'Recovery rates'),
            ('diagnosis', 'Diagnostic results')
        ]

        for concept_id, description in healthcare_concepts:
            concept_node = Node(
                id=f"healthcare_concept_{concept_id}",
                type=NodeType.CONCEPT,
                label=concept_id.title(),
                properties={
                    'domain': 'healthcare',
                    'description': description,
                    'category': 'healthcare_metric'
                }
            )
            graph.add_node(concept_node)

        return graph

    def get_conversion_stats(self, graph: KnowledgeGraph) -> Dict[str, Any]:
        """
        Get statistics about the graph conversion.

        Args:
            graph: Converted knowledge graph

        Returns:
            Conversion statistics
        """
        stats = {
            'total_nodes': len(graph.nodes),
            'total_edges': len(graph.edges),
            'node_types': {},
            'edge_types': {},
            'chart_nodes': 0,
            'data_nodes': 0,
            'relationship_edges': 0,
            'semantic_edges': 0
        }

        for node in graph.nodes.values():
            node_type = node.type.value
            stats['node_types'][node_type] = stats['node_types'].get(node_type, 0) + 1

            if node.type == NodeType.CHART:
                stats['chart_nodes'] += 1
            elif node.type in [NodeType.METRIC, NodeType.CONCEPT]:
                stats['data_nodes'] += 1

        for edge in graph.edges:
            edge_type = edge.type.value
            stats['edge_types'][edge_type] = stats['edge_types'].get(edge_type, 0) + 1

            if edge.type == EdgeType.CONTAINS:
                stats['relationship_edges'] += 1
            else:
                stats['semantic_edges'] += 1

        return stats







