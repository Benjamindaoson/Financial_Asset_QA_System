"""
Chart Parser for GraphRAG.

This module provides comprehensive chart parsing and understanding capabilities,
identifying chart types, extracting visual elements, and preparing for graph conversion.
Enhanced support for multi-layered charts and dynamic chart analysis.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
from pathlib import Path
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class ChartTypeClassifier:
    """
    Chart type classification using computer vision and deep learning.
    Enhanced for multi-layered and dynamic charts.
    """

    def __init__(self):
        """Initialize chart type classifier."""
        self.chart_types = {
            'bar_chart': 'vertical/horizontal bars',
            'line_chart': 'connected data points',
            'pie_chart': 'circular sectors',
            'scatter_plot': 'individual data points',
            'histogram': 'frequency bars',
            'area_chart': 'filled area under line',
            'box_plot': 'statistical distribution boxes',
            'heatmap': 'color-coded matrix',
            'radar_chart': 'spider web plot',
            'waterfall_chart': 'sequential additions/subtractions',
            # Multi-layered chart types
            'stacked_bar': 'stacked vertical/horizontal bars',
            'grouped_bar': 'grouped bars with multiple series',
            'multi_line': 'multiple connected line series',
            'combo_chart': 'combination of bars and lines',
            'layered_area': 'overlapping filled areas',
            'bubble_chart': 'scatter plot with bubble sizes',
            'candle_stick': 'financial candlestick chart',
            'gantt_chart': 'project timeline bars',
            'treemap': 'hierarchical rectangles',
            'sunburst': 'multi-level pie chart',
            'waterfall_stacked': 'stacked waterfall chart'
        }

        # Multi-layer detection patterns
        self.multi_layer_patterns = {
            'stacked_elements': ['stacked bars', 'layered areas', 'overlapping segments'],
            'grouped_elements': ['grouped bars', 'clustered points', 'parallel lines'],
            'temporal_elements': ['time series', 'sequential data', 'trend lines'],
            'hierarchical_elements': ['nested structures', 'tree layouts', 'parent-child relationships']
        }

    def classify_chart_type(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Classify chart type using multiple heuristics.
        Enhanced for multi-layered chart detection.

        Args:
            image: OpenCV image array

        Returns:
            Classification results with confidence
        """
        results = {}

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Apply multiple classification methods
        methods = [
            self._classify_by_shapes,
            self._classify_by_lines,
            self._classify_by_colors,
            self._classify_by_layout,
            self._classify_multi_layer  # New multi-layer detection
        ]

        scores = {}
        layer_info = {}

        for method in methods:
            if method == self._classify_multi_layer:
                method_scores, method_layers = method(gray, image)
                scores.update(method_scores)
                layer_info.update(method_layers)
            else:
                method_scores = method(gray, image)
                for chart_type, score in method_scores.items():
                    scores[chart_type] = scores.get(chart_type, 0) + score

        # Normalize scores
        if scores:
            total_score = sum(scores.values())
            normalized_scores = {k: v / total_score for k, v in scores.items()}

            # Get top prediction
            best_type = max(normalized_scores, key=normalized_scores.get)
            confidence = normalized_scores[best_type]

            # Determine if multi-layered
            is_multi_layer = self._is_multi_layer_chart(best_type, layer_info)

            results = {
                'chart_type': best_type,
                'confidence': confidence,
                'all_scores': normalized_scores,
                'description': self.chart_types.get(best_type, 'unknown chart type'),
                'is_multi_layer': is_multi_layer,
                'layer_info': layer_info,
                'complexity': self._calculate_complexity(layer_info)
            }

        return results

    def _classify_multi_layer(self, gray: np.ndarray, color_img: np.ndarray) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """
        Classify multi-layered chart characteristics.

        Returns:
            Tuple of (scores_dict, layer_info_dict)
        """
        scores = {}
        layer_info = {}

        height, width = gray.shape[:2]

        # Analyze layering patterns
        layer_analysis = self._analyze_layer_patterns(gray, color_img)

        # Detect stacked elements
        stacked_score = self._detect_stacked_elements(gray, color_img)
        if stacked_score > 0.5:
            scores['stacked_bar'] = stacked_score * 0.8
            scores['layered_area'] = stacked_score * 0.6
            layer_info['stacked_elements'] = True

        # Detect grouped elements
        grouped_score = self._detect_grouped_elements(gray, color_img)
        if grouped_score > 0.5:
            scores['grouped_bar'] = grouped_score * 0.8
            scores['multi_line'] = grouped_score * 0.7
            layer_info['grouped_elements'] = True

        # Detect temporal sequences
        temporal_score = self._detect_temporal_elements(gray, color_img)
        if temporal_score > 0.5:
            scores['multi_line'] = max(scores.get('multi_line', 0), temporal_score * 0.6)
            scores['combo_chart'] = temporal_score * 0.5
            layer_info['temporal_elements'] = True

        # Detect hierarchical structures
        hierarchy_score = self._detect_hierarchical_elements(gray, color_img)
        if hierarchy_score > 0.5:
            scores['treemap'] = hierarchy_score * 0.7
            scores['sunburst'] = hierarchy_score * 0.6
            layer_info['hierarchical_elements'] = True

        layer_info.update({
            'layer_count': len([k for k in layer_info.keys() if k.endswith('_elements')]),
            'complexity_score': sum(scores.values()) / max(len(scores), 1),
            'pattern_analysis': layer_analysis
        })

        return scores, layer_info

    def _analyze_layer_patterns(self, gray: np.ndarray, color_img: np.ndarray) -> Dict[str, Any]:
        """Analyze different layering patterns in the chart."""
        patterns = {}

        # Color layer analysis
        if len(color_img.shape) == 3:
            hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV)
            color_layers = self._identify_color_layers(hsv)
            patterns['color_layers'] = color_layers

        # Structural layer analysis
        structural_layers = self._identify_structural_layers(gray)
        patterns['structural_layers'] = structural_layers

        # Edge layer analysis
        edges = cv2.Canny(gray, 50, 150)
        edge_layers = self._identify_edge_layers(edges)
        patterns['edge_layers'] = edge_layers

        return patterns

    def _identify_color_layers(self, hsv: np.ndarray) -> Dict[str, Any]:
        """Identify distinct color layers."""
        # Quantize colors and find clusters
        pixels = hsv.reshape(-1, 3)

        # Simple color clustering (could use k-means for better results)
        unique_colors = np.unique(pixels, axis=0)
        color_count = len(unique_colors)

        # Analyze color distribution
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
        dominant_colors = np.sum(hist > hist.max() * 0.01)  # Colors above 1% threshold

        return {
            'unique_colors': color_count,
            'dominant_colors': int(dominant_colors),
            'color_distribution': 'clustered' if color_count < 20 else 'diverse'
        }

    def _identify_structural_layers(self, gray: np.ndarray) -> Dict[str, Any]:
        """Identify structural layers in the image."""
        # Find contours at different scales
        layers = {}

        for scale in [1, 2, 4]:  # Multi-scale analysis
            scaled = cv2.resize(gray, None, fx=1/scale, fy=1/scale)
            contours, _ = cv2.findContours(scaled, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            layers[f'scale_{scale}'] = len(contours)

        # Analyze contour hierarchy
        contours, hierarchy = cv2.findContours(gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if hierarchy is not None:
            hierarchy = hierarchy[0]
            parent_contours = sum(1 for h in hierarchy if h[3] == -1)  # Root contours
            child_contours = sum(1 for h in hierarchy if h[3] != -1)   # Child contours

            layers.update({
                'parent_contours': parent_contours,
                'child_contours': child_contours,
                'hierarchy_depth': self._calculate_hierarchy_depth(hierarchy)
            })

        return layers

    def _identify_edge_layers(self, edges: np.ndarray) -> Dict[str, Any]:
        """Identify edge layers and patterns."""
        # Analyze edge distribution
        height, width = edges.shape
        edge_density = np.sum(edges > 0) / (height * width)

        # Find edge clusters
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        edge_clusters = len(contours)

        return {
            'edge_density': edge_density,
            'edge_clusters': edge_clusters,
            'edge_pattern': 'dense' if edge_density > 0.1 else 'sparse'
        }

    def _calculate_hierarchy_depth(self, hierarchy: np.ndarray) -> int:
        """Calculate the depth of contour hierarchy."""
        if hierarchy is None or len(hierarchy) == 0:
            return 0

        max_depth = 0
        for i, h in enumerate(hierarchy):
            depth = 0
            current = i
            while h[3] != -1:  # Has parent
                depth += 1
                current = h[3]
                h = hierarchy[current]
                if depth > 100:  # Prevent infinite loops
                    break
            max_depth = max(max_depth, depth)

        return max_depth

    def _detect_stacked_elements(self, gray: np.ndarray, color_img: np.ndarray) -> float:
        """Detect stacked/overlayed elements."""
        height, width = gray.shape

        # Look for vertical stacking patterns
        vertical_slices = []
        for x in range(0, width, width//20):  # Sample vertical slices
            slice_data = gray[:, x:x+max(1, width//50)]
            if slice_data.size > 0:
                vertical_slices.append(np.mean(slice_data, axis=1))

        # Analyze stacking patterns
        stacked_score = 0
        if len(vertical_slices) > 1:
            # Compare adjacent slices for stacking patterns
            for i in range(len(vertical_slices) - 1):
                correlation = np.corrcoef(vertical_slices[i], vertical_slices[i+1])[0, 1]
                if correlation > 0.8:  # High correlation indicates stacking
                    stacked_score += 0.2

        stacked_score = min(stacked_score, 1.0)

        # Color-based stacking detection
        if len(color_img.shape) == 3:
            # Look for layered color patterns
            hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            sat_mean = np.mean(saturation)

            if sat_mean > 100:  # High saturation might indicate layered colors
                stacked_score += 0.3

        return min(stacked_score, 1.0)

    def _detect_grouped_elements(self, gray: np.ndarray, color_img: np.ndarray) -> float:
        """Detect grouped/clustered elements."""
        # Find contours
        contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return 0.0

        # Analyze contour clustering
        centers = []
        for contour in contours:
            M = cv2.moments(contour)
            if M['m00'] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                centers.append((cx, cy))

        if len(centers) < 3:
            return 0.0

        # Calculate clustering score based on center proximity
        centers = np.array(centers)
        distances = []

        for i, center1 in enumerate(centers):
            for j, center2 in enumerate(centers):
                if i != j:
                    dist = np.linalg.norm(center1 - center2)
                    distances.append(dist)

        if distances:
            avg_distance = np.mean(distances)
            height, width = gray.shape
            max_dimension = max(height, width)

            # Normalize distance and calculate grouping score
            normalized_distance = avg_distance / max_dimension

            if normalized_distance < 0.3:  # Close together = grouped
                grouped_score = 1.0 - normalized_distance / 0.3
            else:
                grouped_score = 0.0
        else:
            grouped_score = 0.0

        return grouped_score

    def _detect_temporal_elements(self, gray: np.ndarray, color_img: np.ndarray) -> float:
        """Detect temporal/sequential elements."""
        height, width = gray.shape

        # Look for horizontal progression patterns
        horizontal_slices = []
        for y in range(0, height, height//20):  # Sample horizontal slices
            slice_data = gray[y:y+max(1, height//50), :]
            if slice_data.size > 0:
                horizontal_slices.append(np.mean(slice_data, axis=0))

        # Analyze temporal patterns
        temporal_score = 0
        if len(horizontal_slices) > 1:
            # Look for progressive patterns
            gradients = []
            for slice_data in horizontal_slices:
                if len(slice_data) > 1:
                    gradient = np.gradient(slice_data)
                    gradients.append(np.std(gradient))  # Variation in gradient

            if gradients:
                avg_gradient_var = np.mean(gradients)
                # High gradient variation might indicate temporal progression
                temporal_score = min(avg_gradient_var / 50, 1.0)

        # Edge flow analysis
        edges = cv2.Canny(gray, 50, 150)
        edge_flow = self._analyze_edge_flow(edges)
        temporal_score += edge_flow * 0.5

        return min(temporal_score, 1.0)

    def _detect_hierarchical_elements(self, gray: np.ndarray, color_img: np.ndarray) -> float:
        """Detect hierarchical/nested elements."""
        # Analyze contour hierarchy
        contours, hierarchy = cv2.findContours(gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if hierarchy is None or len(contours) < 2:
            return 0.0

        hierarchy = hierarchy[0]

        # Count nested relationships
        nested_count = 0
        max_nesting = 0

        for i, h in enumerate(hierarchy):
            if h[3] != -1:  # Has parent
                nested_count += 1

                # Calculate nesting depth
                depth = 1
                current = h[3]
                while hierarchy[current][3] != -1 and depth < 10:
                    depth += 1
                    current = hierarchy[current][3]

                max_nesting = max(max_nesting, depth)

        total_contours = len(contours)
        if total_contours == 0:
            return 0.0

        # Calculate hierarchy score
        nesting_ratio = nested_count / total_contours
        hierarchy_score = min(nesting_ratio * 2, 1.0)  # Scale up nesting importance

        # Add depth bonus
        if max_nesting > 2:
            hierarchy_score += 0.3
        if max_nesting > 3:
            hierarchy_score += 0.2

        return min(hierarchy_score, 1.0)

    def _analyze_edge_flow(self, edges: np.ndarray) -> float:
        """Analyze edge flow patterns."""
        height, width = edges.shape

        # Sample edge directions across the image
        directions = []
        step = max(1, min(height, width) // 20)

        for y in range(0, height, step):
            for x in range(0, width - step, step):
                # Simple edge direction estimation
                if edges[y, x] > 0:
                    # Look at neighboring pixels
                    right = edges[y, x + 1] if x + 1 < width else 0
                    down = edges[y + 1, x] if y + 1 < height else 0

                    if right > 0 or down > 0:
                        directions.append(1)  # Continuing edge
                    else:
                        directions.append(0)  # Isolated edge

        if not directions:
            return 0.0

        # Flow score based on edge continuity
        flow_ratio = sum(directions) / len(directions)
        return flow_ratio

    def _is_multi_layer_chart(self, chart_type: str, layer_info: Dict[str, Any]) -> bool:
        """Determine if chart is multi-layered."""
        # Check explicit multi-layer types
        if chart_type in ['stacked_bar', 'grouped_bar', 'multi_line', 'combo_chart',
                         'layered_area', 'bubble_chart', 'sunburst', 'treemap']:
            return True

        # Check layer indicators
        layer_indicators = sum(1 for k, v in layer_info.items()
                             if k.endswith('_elements') and v is True)

        return layer_indicators >= 2

    def _calculate_complexity(self, layer_info: Dict[str, Any]) -> str:
        """Calculate chart complexity level."""
        layer_count = layer_info.get('layer_count', 0)
        complexity_score = layer_info.get('complexity_score', 0)

        if complexity_score > 0.8 or layer_count >= 3:
            return 'high'
        elif complexity_score > 0.5 or layer_count >= 2:
            return 'medium'
        elif complexity_score > 0.2 or layer_count >= 1:
            return 'low'
        else:
            return 'simple'

    def _classify_by_shapes(self, gray: np.ndarray, color_img: np.ndarray) -> Dict[str, float]:
        """Classify based on detected shapes."""
        scores = {}

        # Find contours
        contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return scores

        # Analyze contour properties
        rect_count = 0
        circle_count = 0
        line_count = 0

        height, width = gray.shape[:2]

        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)

            # Skip very small contours
            if w < 10 or h < 10:
                continue

            aspect_ratio = w / max(h, 1)
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)

            # Classify shape
            if 0.8 <= aspect_ratio <= 1.2 and area > 100:  # Square-like
                rect_count += 1
            elif aspect_ratio > 2:  # Horizontal rectangle (bar)
                rect_count += 1
            elif aspect_ratio < 0.5:  # Vertical rectangle (bar)
                rect_count += 1

            # Check for circles (pie chart)
            area_ratio = area / (perimeter * perimeter / (4 * np.pi)) if perimeter > 0 else 0
            if 0.7 <= area_ratio <= 1.3:
                circle_count += 1

        # Assign scores based on shape counts
        if rect_count > 5:
            scores['bar_chart'] = min(rect_count / 10, 1.0)
            scores['histogram'] = min(rect_count / 15, 0.8)

        if circle_count > 0:
            scores['pie_chart'] = min(circle_count / 3, 1.0)

        return scores

    def _classify_by_lines(self, gray: np.ndarray, color_img: np.ndarray) -> Dict[str, float]:
        """Classify based on line patterns."""
        scores = {}

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Line detection
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                               minLineLength=30, maxLineGap=10)

        if lines is not None:
            line_count = len(lines[0])
            height, width = gray.shape[:2]

            # Analyze line orientations
            horizontal_lines = 0
            vertical_lines = 0
            diagonal_lines = 0

            for line in lines[0]:
                x1, y1, x2, y2 = line[0]
                angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

                if angle < 10 or angle > 170:  # Horizontal
                    horizontal_lines += 1
                elif 80 < angle < 100:  # Vertical
                    vertical_lines += 1
                else:  # Diagonal
                    diagonal_lines += 1

            # Grid-like pattern (axes and grid lines)
            if horizontal_lines > 2 and vertical_lines > 2:
                scores['line_chart'] = min((horizontal_lines + vertical_lines) / 20, 1.0)
                scores['bar_chart'] = min((horizontal_lines + vertical_lines) / 15, 0.7)

            # Many diagonal lines might indicate scatter plot
            if diagonal_lines > line_count * 0.3:
                scores['scatter_plot'] = min(diagonal_lines / line_count, 0.8)

        return scores

    def _classify_by_colors(self, gray: np.ndarray, color_img: np.ndarray) -> Dict[str, float]:
        """Classify based on color patterns."""
        scores = {}

        if len(color_img.shape) == 2:  # Grayscale
            return scores

        # Analyze color distribution
        hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])

        # Normalize histogram
        hist = cv2.normalize(hist, hist).flatten()

        # Count dominant colors
        dominant_colors = np.sum(hist > 0.01)  # Colors with >1% presence

        # Different chart types have different color patterns
        if dominant_colors > 10:  # Many colors
            scores['heatmap'] = 0.6
        elif dominant_colors > 5:  # Several colors
            scores['pie_chart'] = 0.5
            scores['bar_chart'] = 0.4
        else:  # Few colors
            scores['line_chart'] = 0.5
            scores['area_chart'] = 0.4

        return scores

    def _classify_by_layout(self, gray: np.ndarray, color_img: np.ndarray) -> Dict[str, float]:
        """Classify based on overall layout patterns."""
        scores = {}

        height, width = gray.shape[:2]

        # Divide image into regions
        regions = {
            'top': gray[:height//4, :],
            'bottom': gray[3*height//4:, :],
            'left': gray[:, :width//4],
            'right': gray[:, 3*width//4:],
            'center': gray[height//4:3*height//4, width//4:3*width//4]
        }

        # Analyze region properties
        region_scores = {}
        for region_name, region in regions.items():
            # Edge density
            edges = cv2.Canny(region, 50, 150)
            edge_density = np.sum(edges > 0) / region.size

            # Text-like regions (high contrast)
            _, thresh = cv2.threshold(region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text_density = np.sum(thresh > 127) / region.size

            region_scores[region_name] = {
                'edge_density': edge_density,
                'text_density': text_density
            }

        # Layout-based classification
        center_edges = region_scores['center']['edge_density']
        bottom_text = region_scores['bottom']['text_density']

        if center_edges > 0.05 and bottom_text > 0.3:  # Data in center, labels at bottom
            scores['bar_chart'] = 0.7
            scores['line_chart'] = 0.6

        if center_edges < 0.02 and bottom_text > 0.4:  # Mostly text, few edges
            scores['table'] = 0.8  # Might be a table, not chart

        return scores


class ChartElementExtractor:
    """
    Extract individual elements from charts (axes, legends, data points, etc.)
    """

    def __init__(self):
        """Initialize chart element extractor."""
        pass

    def extract_elements(self, image: np.ndarray, chart_type: str) -> Dict[str, Any]:
        """
        Extract chart elements based on type.

        Args:
            image: OpenCV image array
            chart_type: Classified chart type

        Returns:
            Extracted elements
        """
        elements = {
            'axes': self._extract_axes(image),
            'legend': self._extract_legend(image),
            'title': self._extract_title(image),
            'data_regions': self._extract_data_regions(image, chart_type),
            'labels': self._extract_labels(image)
        }

        return elements

    def _extract_axes(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract chart axes."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        edges = cv2.Canny(gray, 50, 150)

        # Find lines
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=50, maxLineGap=10)

        axes = {'x_axis': None, 'y_axis': None, 'grid_lines': []}

        if lines is not None:
            height, width = gray.shape[:2]

            for line in lines[0]:
                x1, y1, x2, y2 = line[0]

                # Check for horizontal axis (usually at bottom)
                if abs(y1 - height) < 50 and abs(y2 - height) < 50:
                    if abs(x2 - x1) > width * 0.5:  # Significant length
                        axes['x_axis'] = {
                            'start': (x1, y1),
                            'end': (x2, y2),
                            'orientation': 'horizontal'
                        }

                # Check for vertical axis (usually at left)
                elif abs(x1 - 0) < 50 and abs(x2 - 0) < 50:
                    if abs(y2 - y1) > height * 0.5:  # Significant length
                        axes['y_axis'] = {
                            'start': (x1, y1),
                            'end': (x2, y2),
                            'orientation': 'vertical'
                        }

                # Grid lines (shorter lines)
                else:
                    axes['grid_lines'].append({
                        'start': (x1, y1),
                        'end': (x2, y2)
                    })

        return axes

    def _extract_legend(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Extract chart legend."""
        # Simplified legend detection
        # Look for region with colored boxes and text
        height, width = image.shape[:2]

        # Common legend positions
        candidate_regions = [
            (width - width//4, 0, width, height//2),  # Top-right
            (0, height - height//4, width//2, height),  # Bottom-left
            (width - width//3, height - height//3, width, height)  # Bottom-right
        ]

        for x1, y1, x2, y2 in candidate_regions:
            region = image[y1:y2, x1:x2]

            # Analyze region for legend characteristics
            if self._is_legend_region(region):
                return {
                    'bbox': (x1, y1, x2, y2),
                    'confidence': 0.8,
                    'position': 'detected'
                }

        return None

    def _is_legend_region(self, region: np.ndarray) -> bool:
        """Check if region contains legend characteristics."""
        if region.size == 0:
            return False

        # Look for multiple distinct colors (legend items)
        if len(region.shape) == 3:
            # Reshape to get color distribution
            pixels = region.reshape(-1, 3)
            unique_colors = len(np.unique(pixels, axis=0))

            # Legends typically have multiple distinct colors
            return unique_colors > 5

        return False

    def _extract_title(self, image: np.ndarray) -> Optional[str]:
        """Extract chart title."""
        # Simplified title extraction
        # Assume title is in top portion of image
        height, width = image.shape[:2]
        title_region = image[:height//6, :]  # Top 1/6

        # This would integrate with OCR to extract text
        # For now, return placeholder
        return "Chart Title (OCR Required)"

    def _extract_data_regions(self, image: np.ndarray, chart_type: str) -> List[Dict[str, Any]]:
        """Extract data-containing regions."""
        regions = []

        height, width = image.shape[:2]

        # Define likely data regions based on chart type
        if chart_type in ['bar_chart', 'line_chart', 'area_chart']:
            # Main plotting area (center, avoiding axes)
            data_region = {
                'bbox': (width//8, height//6, 7*width//8, 5*height//6),
                'type': 'plot_area',
                'confidence': 0.9
            }
            regions.append(data_region)

        elif chart_type == 'pie_chart':
            # Central circular region
            center_size = min(width, height) // 2
            data_region = {
                'bbox': (width//2 - center_size//2, height//2 - center_size//2,
                        width//2 + center_size//2, height//2 + center_size//2),
                'type': 'pie_area',
                'confidence': 0.8
            }
            regions.append(data_region)

        return regions

    def _extract_labels(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text labels from chart."""
        # This would integrate with OCR
        # For now, return placeholder
        return []


class ChartParser:
    """
    Main chart parser coordinating classification and element extraction.
    """

    def __init__(self):
        """Initialize chart parser."""
        self.classifier = ChartTypeClassifier()
        self.extractor = ChartElementExtractor()

    def parse_chart(self, image: Union[str, Image.Image]) -> Dict[str, Any]:
        """
        Parse chart comprehensively.

        Args:
            image: Chart image path or PIL Image

        Returns:
            Complete chart parsing results
        """
        try:
            # Load image
            if isinstance(image, str):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            # Classify chart type
            classification = self.classifier.classify_chart_type(cv_image)

            # Extract elements
            chart_type = classification.get('chart_type', 'unknown')
            elements = self.extractor.extract_elements(cv_image, chart_type)

            # Combine results
            result = {
                'classification': classification,
                'elements': elements,
                'metadata': {
                    'image_size': pil_image.size,
                    'parsing_confidence': classification.get('confidence', 0.0),
                    'processing_time': 0.0  # Would measure actual time
                }
            }

            return result

        except Exception as e:
            logger.error(f"Failed to parse chart: {e}")
            return {
                'error': str(e),
                'classification': {'chart_type': 'unknown', 'confidence': 0.0},
                'elements': {}
            }

    def get_supported_chart_types(self) -> List[str]:
        """Get list of supported chart types."""
        return list(self.classifier.chart_types.keys())
