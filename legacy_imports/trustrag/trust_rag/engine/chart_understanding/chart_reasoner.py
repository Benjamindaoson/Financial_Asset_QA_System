"""
Chart Reasoner for GraphRAG.

This module provides reasoning capabilities over chart knowledge graphs,
enabling question answering, insight extraction, and chart analysis.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import re

from ...graph_db.graph_types import KnowledgeGraph, Node, Edge, NodeType, EdgeType

logger = logging.getLogger(__name__)


class ChartReasoner:
    """
    Reasoner for chart knowledge graphs.

    Provides capabilities to answer questions about charts, extract insights,
    and perform comparative analysis using graph-based reasoning.
    """

    def __init__(self):
        """Initialize chart reasoner."""
        self.insights_cache = {}

    def reason_about_chart(self, query: str, chart_graph: KnowledgeGraph) -> Dict[str, Any]:
        """
        Reason about a chart using the knowledge graph.

        Args:
            query: Question or query about the chart
            chart_graph: Chart knowledge graph

        Returns:
            Reasoning results with answer and evidence
        """
        try:
            query_type = self._classify_query_type(query)

            if query_type == 'factual':
                result = self._answer_factual_query(query, chart_graph)
            elif query_type == 'comparative':
                result = self._answer_comparative_query(query, chart_graph)
            elif query_type == 'trend':
                result = self._answer_trend_query(query, chart_graph)
            elif query_type == 'insight':
                result = self._extract_insights(chart_graph)
            else:
                result = self._answer_general_query(query, chart_graph)

            # Add metadata
            result['query_type'] = query_type
            result['graph_stats'] = {
                'nodes': len(chart_graph.nodes),
                'edges': len(chart_graph.edges),
                'chart_type': self._get_chart_type(chart_graph)
            }

            return result

        except Exception as e:
            logger.error(f"Failed to reason about chart: {e}")
            return {
                'answer': 'Unable to analyze chart',
                'confidence': 0.0,
                'error': str(e),
                'evidence': []
            }

    def _classify_query_type(self, query: str) -> str:
        """Classify the type of query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ['what is', 'how much', 'what are', 'show me']):
            return 'factual'
        elif any(word in query_lower for word in ['compare', 'vs', 'versus', 'which', 'better', 'higher']):
            return 'comparative'
        elif any(word in query_lower for word in ['trend', 'change', 'over time', 'growth']):
            return 'trend'
        elif any(word in query_lower for word in ['insight', 'analysis', 'summary', 'tell me about']):
            return 'insight'
        else:
            return 'general'

    def _answer_factual_query(self, query: str, graph: KnowledgeGraph) -> Dict[str, Any]:
        """Answer factual questions about the chart."""
        # Extract key terms from query
        key_terms = self._extract_key_terms(query)

        # Find relevant nodes
        relevant_nodes = []
        evidence = []

        for node in graph.nodes.values():
            node_text = f"{node.label} {node.properties}".lower()

            for term in key_terms:
                if term.lower() in node_text:
                    relevant_nodes.append(node)
                    evidence.append({
                        'node_id': node.id,
                        'node_label': node.label,
                        'relevance': 'keyword_match',
                        'matched_term': term
                    })
                    break

        # Generate answer based on relevant nodes
        if relevant_nodes:
            answer = self._generate_answer_from_nodes(relevant_nodes, query)
            confidence = min(len(relevant_nodes) / 5, 1.0)  # Confidence based on evidence count
        else:
            answer = "No relevant information found in the chart."
            confidence = 0.0

        return {
            'answer': answer,
            'confidence': confidence,
            'evidence': evidence[:5],  # Limit evidence
            'relevant_nodes': len(relevant_nodes)
        }

    def _answer_comparative_query(self, query: str, graph: KnowledgeGraph) -> Dict[str, Any]:
        """Answer comparative questions about the chart."""
        # Find comparison edges in the graph
        comparison_edges = [edge for edge in graph.edges
                          if edge.type in [EdgeType.RELATED_TO, EdgeType.SIMILAR_TO]]

        # Look for magnitude comparison edges
        magnitude_comparisons = [edge for edge in comparison_edges
                               if edge.properties.get('comparison_type') == 'magnitude']

        evidence = []
        comparisons = []

        for edge in magnitude_comparisons:
            source_node = graph.nodes.get(edge.source_id)
            target_node = graph.nodes.get(edge.target_id)

            if source_node and target_node:
                source_val = source_node.properties.get('value', 0)
                target_val = target_node.properties.get('value', 0)
                relationship = edge.properties.get('relationship_type', '')

                comparison = {
                    'item1': source_node.label,
                    'item2': target_node.label,
                    'relationship': relationship,
                    'value1': source_val,
                    'value2': target_val,
                    'difference': abs(source_val - target_val)
                }
                comparisons.append(comparison)

                evidence.append({
                    'comparison': comparison,
                    'edge_id': edge.id,
                    'confidence': edge.weight
                })

        # Generate comparative answer
        if comparisons:
            answer = self._generate_comparative_answer(comparisons, query)
            confidence = 0.8
        else:
            answer = "No clear comparisons found in the chart."
            confidence = 0.3

        return {
            'answer': answer,
            'confidence': confidence,
            'evidence': evidence,
            'comparisons': comparisons
        }

    def _answer_trend_query(self, query: str, graph: KnowledgeGraph) -> Dict[str, Any]:
        """Answer trend-related questions about the chart."""
        # Find trend edges
        trend_edges = [edge for edge in graph.edges
                      if 'trend' in edge.properties.get('relationship_type', '')]

        # Find series nodes with trend information
        series_nodes = [node for node in graph.nodes.values()
                       if 'series' in node.id and node.properties.get('trend')]

        evidence = []
        trends = []

        for node in series_nodes:
            trend_info = {
                'series': node.label,
                'trend': node.properties.get('trend'),
                'point_count': node.properties.get('point_count', 0),
                'series_index': node.properties.get('series_index', 0)
            }
            trends.append(trend_info)

            evidence.append({
                'series_node': node.id,
                'trend': trend_info['trend'],
                'confidence': 0.8
            })

        # Analyze trend edges
        for edge in trend_edges:
            trend_type = edge.properties.get('relationship_type', '')
            if trend_type:
                evidence.append({
                    'trend_edge': edge.id,
                    'trend_type': trend_type.replace('_trend', ''),
                    'confidence': edge.weight
                })

        # Generate trend answer
        if trends:
            answer = self._generate_trend_answer(trends, query)
            confidence = 0.85
        else:
            answer = "No clear trends identified in the chart."
            confidence = 0.4

        return {
            'answer': answer,
            'confidence': confidence,
            'evidence': evidence,
            'trends': trends
        }

    def _extract_insights(self, graph: KnowledgeGraph) -> Dict[str, Any]:
        """Extract insights from the chart graph."""
        insights = []
        evidence = []

        # Analyze node types and distributions
        node_types = defaultdict(int)
        for node in graph.nodes.values():
            node_types[node.type] += 1

        # Find key metrics
        metric_nodes = [node for node in graph.nodes.values() if node.type == NodeType.METRIC]
        if metric_nodes:
            values = [node.properties.get('value', 0) for node in metric_nodes]
            max_val = max(values)
            min_val = min(values)
            avg_val = sum(values) / len(values)

            insights.append(f"The chart shows values ranging from {min_val:.2f} to {max_val:.2f}, with an average of {avg_val:.2f}")

            # Find outliers
            outliers = [node for node in metric_nodes
                       if abs(node.properties.get('value', 0) - avg_val) > avg_val * 0.5]

            if outliers:
                outlier_labels = [node.label for node in outliers]
                insights.append(f"Notable outliers: {', '.join(outlier_labels)}")

        # Analyze relationships
        edge_types = defaultdict(int)
        for edge in graph.edges:
            edge_types[edge.type] += 1

        # Find strongly connected components
        if len(graph.nodes) > 3:
            components = self._find_connected_components(graph)
            if len(components) > 1:
                insights.append(f"The chart data forms {len(components)} distinct groups or categories")

        # Chart type insights
        chart_type = self._get_chart_type(graph)
        if chart_type:
            insights.append(f"This appears to be a {chart_type.replace('_', ' ')} showing {self._get_chart_purpose(graph)}")

        return {
            'answer': ' '.join(insights) if insights else 'No significant insights extracted.',
            'confidence': 0.7,
            'evidence': evidence,
            'insights': insights,
            'chart_type': chart_type
        }

    def _answer_general_query(self, query: str, graph: KnowledgeGraph) -> Dict[str, Any]:
        """Answer general questions about the chart."""
        chart_type = self._get_chart_type(graph)
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)

        # Generate general description
        description_parts = []

        if chart_type:
            description_parts.append(f"This is a {chart_type.replace('_', ' ')}")

        description_parts.append(f"containing {node_count} data elements")
        description_parts.append(f"and {edge_count} relationships")

        # Add key metrics if available
        metric_nodes = [node for node in graph.nodes.values() if node.type == NodeType.METRIC]
        if metric_nodes:
            values = [node.properties.get('value', 0) for node in metric_nodes if 'value' in node.properties]
            if values:
                max_val = max(values)
                description_parts.append(f"with values up to {max_val:.2f}")

        answer = '. '.join(description_parts) + '.'

        return {
            'answer': answer,
            'confidence': 0.6,
            'evidence': [],
            'description': 'General chart overview'
        }

    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from query."""
        # Simple term extraction
        import re

        # Remove question words
        query = re.sub(r'\b(what|how|which|where|when|why|who|show|tell|me|about|the|a|an|is|are|was|were)\b',
                      '', query, flags=re.IGNORECASE)

        # Extract remaining words
        words = re.findall(r'\b\w+\b', query.lower())

        # Filter out short words and common terms
        stop_words = {'chart', 'graph', 'data', 'value', 'show', 'display'}
        key_terms = [word for word in words if len(word) > 2 and word not in stop_words]

        return list(set(key_terms))  # Remove duplicates

    def _generate_answer_from_nodes(self, nodes: List[Node], query: str) -> str:
        """Generate answer from relevant nodes."""
        if not nodes:
            return "No relevant information found."

        # Sort nodes by relevance (simplified)
        nodes.sort(key=lambda n: n.properties.get('value', 0), reverse=True)

        answers = []

        for node in nodes[:3]:  # Limit to top 3
            label = node.label
            value = node.properties.get('value')

            if value is not None:
                if isinstance(value, float):
                    answers.append(f"{label}: {value:.2f}")
                else:
                    answers.append(f"{label}: {value}")
            else:
                answers.append(f"{label}")

        return "; ".join(answers)

    def _generate_comparative_answer(self, comparisons: List[Dict], query: str) -> str:
        """Generate comparative answer."""
        if not comparisons:
            return "No comparisons available."

        # Sort by difference
        comparisons.sort(key=lambda c: c['difference'], reverse=True)

        answers = []

        for comp in comparisons[:3]:  # Top 3 comparisons
            item1, item2 = comp['item1'], comp['item2']
            relationship = comp['relationship'].replace('_', ' ')

            if 'higher' in relationship:
                answers.append(f"{item1} is higher than {item2}")
            elif 'lower' in relationship:
                answers.append(f"{item1} is lower than {item2}")
            else:
                answers.append(f"{item1} {relationship} {item2}")

        return "; ".join(answers)

    def _generate_trend_answer(self, trends: List[Dict], query: str) -> str:
        """Generate trend answer."""
        if not trends:
            return "No trend information available."

        trend_descriptions = []

        for trend in trends:
            series = trend['series']
            trend_type = trend['trend']
            point_count = trend['point_count']

            if trend_type == 'increasing':
                desc = f"{series} shows an upward trend"
            elif trend_type == 'decreasing':
                desc = f"{series} shows a downward trend"
            else:
                desc = f"{series} shows a {trend_type} pattern"

            desc += f" over {point_count} data points"
            trend_descriptions.append(desc)

        return "; ".join(trend_descriptions)

    def _get_chart_type(self, graph: KnowledgeGraph) -> str:
        """Determine chart type from graph."""
        chart_nodes = [node for node in graph.nodes.values() if node.type == NodeType.CHART]

        if chart_nodes:
            return chart_nodes[0].properties.get('chart_type', 'unknown')

        return 'unknown'

    def _get_chart_purpose(self, graph: KnowledgeGraph) -> str:
        """Determine chart purpose from content."""
        # Analyze node types and properties
        metric_count = sum(1 for node in graph.nodes.values() if node.type == NodeType.METRIC)

        if metric_count > 5:
            return "multiple data points or categories"
        elif metric_count > 0:
            return "quantitative comparisons"
        else:
            return "categorical information"

    def _find_connected_components(self, graph: KnowledgeGraph) -> List[List[str]]:
        """Find connected components in the graph."""
        # Simple connected components algorithm
        visited = set()
        components = []

        for node_id in graph.nodes:
            if node_id not in visited:
                # BFS to find component
                component = []
                queue = [node_id]

                while queue:
                    current = queue.pop(0)
                    if current not in visited:
                        visited.add(current)
                        component.append(current)

                        # Add neighbors
                        for edge in graph.edges:
                            if edge.source_id == current and edge.target_id not in visited:
                                queue.append(edge.target_id)
                            elif edge.target_id == current and edge.source_id not in visited:
                                queue.append(edge.source_id)

                if component:
                    components.append(component)

        return components

    def extract_chart_insights(self, chart_graph: KnowledgeGraph) -> Dict[str, Any]:
        """
        Extract comprehensive insights from chart graph.

        Args:
            chart_graph: Chart knowledge graph

        Returns:
            Dictionary with various insights
        """
        insights = {
            'summary': self._generate_chart_summary(chart_graph),
            'key_findings': self._extract_key_findings(chart_graph),
            'anomalies': self._detect_anomalies(chart_graph),
            'correlations': self._find_correlations(chart_graph),
            'recommendations': self._generate_recommendations(chart_graph)
        }

        return insights

    def _generate_chart_summary(self, graph: KnowledgeGraph) -> str:
        """Generate a textual summary of the chart."""
        chart_type = self._get_chart_type(graph)
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)

        summary = f"This {chart_type.replace('_', ' ')} contains {node_count} elements "

        # Add data range if available
        values = []
        for node in graph.nodes.values():
            if node.type == NodeType.METRIC and 'value' in node.properties:
                values.append(node.properties['value'])

        if values:
            min_val, max_val = min(values), max(values)
            summary += f"with values ranging from {min_val:.2f} to {max_val:.2f}. "
        else:
            summary += ". "

        summary += f"The data shows {edge_count} relationships between elements."

        return summary

    def _extract_key_findings(self, graph: KnowledgeGraph) -> List[str]:
        """Extract key findings from the chart."""
        findings = []

        # Find maximum and minimum values
        values = []
        value_nodes = []

        for node in graph.nodes.values():
            if node.type == NodeType.METRIC and 'value' in node.properties:
                values.append(node.properties['value'])
                value_nodes.append(node)

        if values:
            max_idx = values.index(max(values))
            min_idx = values.index(min(values))

            findings.append(f"Highest value: {value_nodes[max_idx].label} ({max(values):.2f})")
            findings.append(f"Lowest value: {value_nodes[min_idx].label} ({min(values):.2f})")

        # Find trends
        trend_edges = [edge for edge in graph.edges
                      if 'trend' in edge.properties.get('relationship_type', '')]

        if trend_edges:
            trend_types = [edge.properties.get('relationship_type', '').replace('_trend', '')
                          for edge in trend_edges]
            unique_trends = list(set(trend_types))
            findings.append(f"Detected trends: {', '.join(unique_trends)}")

        return findings

    def _detect_anomalies(self, graph: KnowledgeGraph) -> List[str]:
        """Detect anomalies in chart data."""
        anomalies = []

        # Find outlier values
        values = []
        value_nodes = []

        for node in graph.nodes.values():
            if node.type == NodeType.METRIC and 'value' in node.properties:
                values.append(node.properties['value'])
                value_nodes.append(node)

        if len(values) > 3:
            mean_val = sum(values) / len(values)
            std_val = (sum((v - mean_val) ** 2 for v in values) / len(values)) ** 0.5

            for node, value in zip(value_nodes, values):
                z_score = abs(value - mean_val) / (std_val + 1e-6)
                if z_score > 2.0:  # More than 2 standard deviations
                    anomalies.append(f"Outlier detected: {node.label} ({value:.2f}, z-score: {z_score:.2f})")

        return anomalies

    def _find_correlations(self, graph: KnowledgeGraph) -> List[str]:
        """Find correlations in chart data."""
        correlations = []

        # Simple correlation detection for paired data
        # This is a placeholder for more sophisticated correlation analysis

        return correlations

    def _generate_recommendations(self, graph: KnowledgeGraph) -> List[str]:
        """Generate recommendations based on chart analysis."""
        recommendations = []

        chart_type = self._get_chart_type(graph)

        if chart_type == 'bar_chart':
            recommendations.append("Consider using a line chart if showing trends over time")
        elif chart_type == 'pie_chart':
            metric_count = sum(1 for node in graph.nodes.values() if node.type == NodeType.METRIC)
            if metric_count > 7:
                recommendations.append("Pie charts work best with 5-7 categories; consider grouping smaller segments")

        # Data quality recommendations
        values = [node.properties.get('value', 0)
                 for node in graph.nodes.values()
                 if node.type == NodeType.METRIC and 'value' in node.properties]

        if values and max(values) / (min(values) + 1e-6) > 100:
            recommendations.append("Large value range detected; consider using a logarithmic scale")

        return recommendations







