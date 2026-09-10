"""
Chart Data Extractor for GraphRAG.

This module extracts structured data from parsed charts, including
numerical values, labels, and relationships for graph construction.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import re

logger = logging.getLogger(__name__)


class ChartDataExtractor:
    """
    Extract structured data from charts using computer vision and OCR.
    """

    def __init__(self, ocr_engine=None):
        """
        Initialize chart data extractor.

        Args:
            ocr_engine: OCR engine for text extraction
        """
        self.ocr_engine = ocr_engine

        # Patterns for data extraction
        self.number_patterns = [
            re.compile(r'\$?[\d,]+(?:\.\d+)?(?:k|m|b|%)?', re.IGNORECASE),
            re.compile(r'\d+(?:\.\d+)?'),
        ]

        self.label_patterns = [
            re.compile(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'),  # Title case words
            re.compile(r'\d{4}(?:-\d{2})?'),  # Years/dates
        ]

    def extract_data(self, image: Union[str, Image.Image], parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured data from chart.

        Args:
            image: Chart image
            parsing_result: Chart parsing results from ChartParser

        Returns:
            Extracted structured data
        """
        try:
            # Load image
            if isinstance(image, str):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            chart_type = parsing_result.get('classification', {}).get('chart_type', 'unknown')

            # Extract data based on chart type
            if chart_type == 'bar_chart':
                data = self._extract_bar_chart_data(cv_image, parsing_result)
            elif chart_type == 'line_chart':
                data = self._extract_line_chart_data(cv_image, parsing_result)
            elif chart_type == 'pie_chart':
                data = self._extract_pie_chart_data(cv_image, parsing_result)
            elif chart_type == 'scatter_plot':
                data = self._extract_scatter_plot_data(cv_image, parsing_result)
            else:
                data = self._extract_generic_chart_data(cv_image, parsing_result)

            # Extract text labels using OCR if available
            text_data = self._extract_text_labels(cv_image, parsing_result)

            # Combine and validate data
            combined_data = self._combine_and_validate_data(data, text_data, parsing_result)

            return combined_data

        except Exception as e:
            logger.error(f"Failed to extract chart data: {e}")
            return {'error': str(e), 'data_points': []}

    def _extract_bar_chart_data(self, image: np.ndarray, parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from bar charts."""
        data = {
            'series': [],
            'categories': [],
            'values': [],
            'confidence': 0.0
        }

        try:
            # Find bars in the image
            bars = self._detect_bars(image)

            if bars:
                # Sort bars by position (left to right, bottom to top)
                bars.sort(key=lambda b: (b['x'], -b['y']))

                # Extract values (heights for vertical bars, widths for horizontal)
                for i, bar in enumerate(bars):
                    value = self._estimate_bar_value(bar, parsing_result)
                    data['values'].append({
                        'index': i,
                        'value': value,
                        'position': (bar['x'], bar['y']),
                        'dimensions': (bar['w'], bar['h'])
                    })

                data['confidence'] = min(len(bars) / 10, 1.0)  # Higher confidence with more bars

        except Exception as e:
            logger.warning(f"Failed to extract bar chart data: {e}")

        return data

    def _extract_line_chart_data(self, image: np.ndarray, parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from line charts."""
        data = {
            'series': [],
            'data_points': [],
            'trends': [],
            'confidence': 0.0
        }

        try:
            # Detect line patterns
            lines = self._detect_lines(image)

            for line_idx, line_points in enumerate(lines):
                series_data = []

                for point in line_points:
                    # Estimate value from y-coordinate
                    value = self._estimate_coordinate_value(point, parsing_result, axis='y')
                    series_data.append({
                        'x': point[0],
                        'y': point[1],
                        'value': value,
                        'series_index': line_idx
                    })

                if series_data:
                    data['series'].append({
                        'index': line_idx,
                        'points': series_data,
                        'trend': self._calculate_trend(series_data)
                    })

                data['confidence'] = min(len(lines) / 3, 1.0)

        except Exception as e:
            logger.warning(f"Failed to extract line chart data: {e}")

        return data

    def _extract_pie_chart_data(self, image: np.ndarray, parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from pie charts."""
        data = {
            'segments': [],
            'total_value': 0,
            'confidence': 0.0
        }

        try:
            # Detect circular segments
            segments = self._detect_pie_segments(image)

            total_angle = 0
            for segment in segments:
                angle = segment['angle']
                percentage = angle / 360.0
                value = percentage * 100  # Assume percentage values

                data['segments'].append({
                    'angle': angle,
                    'percentage': percentage,
                    'value': value,
                    'color': segment.get('color', 'unknown'),
                    'position': segment.get('position', (0, 0))
                })

                total_angle += angle

            data['total_value'] = sum(s['value'] for s in data['segments'])
            data['confidence'] = min(total_angle / 360.0, 1.0)

        except Exception as e:
            logger.warning(f"Failed to extract pie chart data: {e}")

        return data

    def _extract_scatter_plot_data(self, image: np.ndarray, parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from scatter plots."""
        data = {
            'points': [],
            'clusters': [],
            'confidence': 0.0
        }

        try:
            # Detect individual data points
            points = self._detect_scatter_points(image)

            for point in points:
                x_value = self._estimate_coordinate_value((point[0], point[1]), parsing_result, axis='x')
                y_value = self._estimate_coordinate_value((point[0], point[1]), parsing_result, axis='y')

                data['points'].append({
                    'x': point[0],
                    'y': point[1],
                    'x_value': x_value,
                    'y_value': y_value,
                    'color': self._get_point_color(image, point)
                })

            data['confidence'] = min(len(points) / 20, 1.0)  # Confidence based on point count

        except Exception as e:
            logger.warning(f"Failed to extract scatter plot data: {e}")

        return data

    def _extract_generic_chart_data(self, image: np.ndarray, parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from unknown chart types using generic methods."""
        data = {
            'regions': [],
            'patterns': [],
            'confidence': 0.3  # Lower confidence for generic extraction
        }

        try:
            # Detect regions of interest
            regions = self._detect_regions_of_interest(image)

            for region in regions:
                region_data = {
                    'bbox': region['bbox'],
                    'intensity': region['intensity'],
                    'area': region['area'],
                    'estimated_value': self._estimate_region_value(region, parsing_result)
                }
                data['regions'].append(region_data)

        except Exception as e:
            logger.warning(f"Failed to extract generic chart data: {e}")

        return data

    def _extract_text_labels(self, image: np.ndarray, parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text labels using OCR."""
        text_data = {
            'x_labels': [],
            'y_labels': [],
            'title': '',
            'legend_labels': [],
            'confidence': 0.0
        }

        try:
            if self.ocr_engine:
                # Convert to PIL for OCR
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

                # OCR the entire image
                ocr_result = self.ocr_engine.extract_text(pil_image)

                if ocr_result.get('text'):
                    text = ocr_result['text']

                    # Extract potential labels
                    words = text.split()

                    # Classify words as potential labels
                    for word in words:
                        if self._is_potential_label(word):
                            # Determine position based on chart elements
                            position = self._classify_label_position(word, parsing_result)
                            text_data[f'{position}_labels'].append(word)

                    text_data['confidence'] = ocr_result.get('confidence', 0.0)

        except Exception as e:
            logger.warning(f"Failed to extract text labels: {e}")

        return text_data

    def _combine_and_validate_data(self, chart_data: Dict[str, Any],
                                 text_data: Dict[str, Any],
                                 parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Combine and validate extracted data."""
        combined = {
            'chart_data': chart_data,
            'text_data': text_data,
            'validation': {},
            'final_data': [],
            'confidence': 0.0
        }

        try:
            # Basic validation
            validation = self._validate_extracted_data(chart_data, text_data)
            combined['validation'] = validation

            # Create final structured data
            final_data = self._create_structured_data(chart_data, text_data, parsing_result)
            combined['final_data'] = final_data

            # Calculate overall confidence
            chart_conf = chart_data.get('confidence', 0.0)
            text_conf = text_data.get('confidence', 0.0)
            validation_score = 1.0 if validation['is_valid'] else 0.5

            combined['confidence'] = (chart_conf + text_conf + validation_score) / 3.0

        except Exception as e:
            logger.warning(f"Failed to combine and validate data: {e}")

        return combined

    def _detect_bars(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect bars in bar chart."""
        bars = []

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # Filter for bar-like shapes
                aspect_ratio = h / max(w, 1)
                if 1.5 < aspect_ratio < 10 and w > 5 and h > 10:  # Tall rectangles
                    bars.append({
                        'x': x, 'y': y, 'w': w, 'h': h,
                        'area': w * h,
                        'aspect_ratio': aspect_ratio
                    })

        except Exception as e:
            logger.warning(f"Failed to detect bars: {e}")

        return bars

    def _detect_lines(self, image: np.ndarray) -> List[List[Tuple[int, int]]]:
        """Detect line patterns in line charts."""
        lines = []

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            edges = cv2.Canny(gray, 50, 150)

            # Use Hough transform to find lines
            hough_lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                                        minLineLength=20, maxLineGap=10)

            if hough_lines is not None:
                # Group lines into connected components (simplified)
                line_points = []
                for line in hough_lines:
                    x1, y1, x2, y2 = line[0]
                    line_points.extend([(x1, y1), (x2, y2)])

                # Simple clustering - group nearby points
                if line_points:
                    lines.append(line_points[:20])  # Take first line as example

        except Exception as e:
            logger.warning(f"Failed to detect lines: {e}")

        return lines

    def _detect_pie_segments(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect pie chart segments."""
        segments = []

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

            # Detect circles
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20,
                                     param1=50, param2=30, minRadius=20, maxRadius=200)

            if circles is not None:
                # For pie charts, we estimate segments based on color changes
                # This is a simplified approach
                height, width = gray.shape[:2]
                center = (width // 2, height // 2)

                # Sample points around the circle
                angles = np.linspace(0, 2*np.pi, 12, endpoint=False)
                radius = min(width, height) // 3

                colors = []
                for angle in angles:
                    x = int(center[0] + radius * np.cos(angle))
                    y = int(center[1] + radius * np.sin(angle))

                    if 0 <= x < width and 0 <= y < height:
                        if len(image.shape) == 3:
                            color = tuple(image[y, x])
                        else:
                            color = (gray[y, x],)
                        colors.append(color)

                # Group similar colors (simplified segment detection)
                unique_colors = list(set(colors))
                for color in unique_colors:
                    count = colors.count(color)
                    angle = (count / len(colors)) * 360
                    segments.append({
                        'color': color,
                        'angle': angle,
                        'position': center
                    })

        except Exception as e:
            logger.warning(f"Failed to detect pie segments: {e}")

        return segments

    def _detect_scatter_points(self, image: np.ndarray) -> List[Tuple[int, int]]:
        """Detect individual points in scatter plots."""
        points = []

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

            # Simple blob detection
            params = cv2.SimpleBlobDetector_Params()
            params.filterByArea = True
            params.minArea = 5
            params.maxArea = 50
            params.filterByCircularity = True
            params.minCircularity = 0.7

            detector = cv2.SimpleBlobDetector_create(params)
            keypoints = detector.detect(gray)

            for kp in keypoints:
                points.append((int(kp.pt[0]), int(kp.pt[1])))

        except Exception as e:
            logger.warning(f"Failed to detect scatter points: {e}")

        return points

    def _detect_regions_of_interest(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect regions of interest in generic charts."""
        regions = []

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

            # Simple region detection using thresholding
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h

                if area > 100:  # Filter small regions
                    intensity = np.mean(gray[y:y+h, x:x+w])
                    regions.append({
                        'bbox': (x, y, w, h),
                        'area': area,
                        'intensity': intensity
                    })

        except Exception as e:
            logger.warning(f"Failed to detect regions: {e}")

        return regions

    def _estimate_bar_value(self, bar: Dict[str, Any], parsing_result: Dict[str, Any]) -> float:
        """Estimate numerical value from bar dimensions."""
        # Simplified estimation based on bar height
        height = bar['h']

        # Get axis information
        axes = parsing_result.get('elements', {}).get('axes', {})
        y_axis = axes.get('y_axis')

        if y_axis:
            # Estimate scale from axis length
            axis_length = abs(y_axis['end'][1] - y_axis['start'][1])
            scale_factor = 100 / max(axis_length, 1)  # Assume 100 unit range
            return height * scale_factor

        return float(height)  # Fallback

    def _estimate_coordinate_value(self, point: Tuple[int, int],
                                 parsing_result: Dict[str, Any],
                                 axis: str) -> float:
        """Estimate value from coordinate position."""
        x, y = point

        axes = parsing_result.get('elements', {}).get('axes', {})
        axis_info = axes.get(f'{axis}_axis')

        if axis_info:
            if axis == 'y':
                # Y-axis: higher values at top
                axis_start, axis_end = axis_info['start'][1], axis_info['end'][1]
                axis_range = abs(axis_end - axis_start)
                relative_pos = (axis_start - y) / max(axis_range, 1)  # Inverted
                return relative_pos * 100  # Assume 0-100 range
            else:
                # X-axis: left to right
                axis_start, axis_end = axis_info['start'][0], axis_info['end'][0]
                axis_range = abs(axis_end - axis_start)
                relative_pos = (x - axis_start) / max(axis_range, 1)
                return relative_pos * 10  # Assume 0-10 range

        return float(x if axis == 'x' else y)  # Fallback

    def _estimate_region_value(self, region: Dict[str, Any], parsing_result: Dict[str, Any]) -> float:
        """Estimate value from region properties."""
        # Simple estimation based on area and intensity
        area = region['area']
        intensity = region['intensity']

        return area * intensity / 10000  # Arbitrary scaling

    def _calculate_trend(self, points: List[Dict[str, Any]]) -> str:
        """Calculate trend direction from data points."""
        if len(points) < 2:
            return 'insufficient_data'

        # Simple trend calculation
        values = [p['value'] for p in points]
        diffs = np.diff(values)

        if len(diffs) == 0:
            return 'flat'

        avg_diff = np.mean(diffs)

        if avg_diff > 1:
            return 'increasing'
        elif avg_diff < -1:
            return 'decreasing'
        else:
            return 'flat'

    def _is_potential_label(self, word: str) -> bool:
        """Check if word could be a chart label."""
        # Filter criteria
        if len(word) < 2 or len(word) > 20:
            return False

        # Check patterns
        for pattern in self.label_patterns:
            if pattern.match(word):
                return True

        return False

    def _classify_label_position(self, word: str, parsing_result: Dict[str, Any]) -> str:
        """Classify label position (x, y, title, legend)."""
        # Simple heuristics
        word_lower = word.lower()

        if any(term in word_lower for term in ['year', 'month', 'quarter']):
            return 'x'  # Likely x-axis label

        if any(term in word_lower for term in ['value', 'amount', 'count']):
            return 'y'  # Likely y-axis label

        if len(word.split()) > 2:
            return 'title'  # Likely title

        return 'legend'  # Default to legend

    def _validate_extracted_data(self, chart_data: Dict[str, Any], text_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted data consistency."""
        validation = {
            'is_valid': True,
            'issues': [],
            'score': 1.0
        }

        # Check data consistency
        if chart_data.get('confidence', 0) < 0.3:
            validation['issues'].append('low_chart_confidence')
            validation['score'] *= 0.8

        if text_data.get('confidence', 0) < 0.5:
            validation['issues'].append('low_text_confidence')
            validation['score'] *= 0.9

        # Check for data-text alignment
        chart_values = self._extract_numeric_values(chart_data)
        text_numbers = self._extract_numeric_values(text_data)

        if chart_values and text_numbers:
            # Check if values are reasonably close
            max_chart = max(chart_values) if chart_values else 0
            max_text = max(text_numbers) if text_numbers else 0

            if abs(max_chart - max_text) / max(max_chart, max_text, 1) > 0.5:
                validation['issues'].append('value_mismatch')
                validation['score'] *= 0.7

        if validation['issues']:
            validation['is_valid'] = False

        return validation

    def _extract_numeric_values(self, data: Dict[str, Any]) -> List[float]:
        """Extract numeric values from data structure."""
        values = []

        def extract_from_dict(d):
            for k, v in d.items():
                if isinstance(v, (int, float)):
                    values.append(float(v))
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            extract_from_dict(item)
                        elif isinstance(item, (int, float)):
                            values.append(float(item))

        extract_from_dict(data)
        return values

    def _create_structured_data(self, chart_data: Dict[str, Any],
                              text_data: Dict[str, Any],
                              parsing_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create final structured data representation."""
        structured_data = []

        try:
            chart_type = parsing_result.get('classification', {}).get('chart_type', 'unknown')

            # Create data entries based on chart type
            if chart_type == 'bar_chart':
                values = chart_data.get('values', [])
                x_labels = text_data.get('x_labels', [])
                y_labels = text_data.get('y_labels', [])

                for i, value_info in enumerate(values):
                    entry = {
                        'type': 'bar_data',
                        'index': i,
                        'value': value_info.get('value', 0),
                        'label': x_labels[i] if i < len(x_labels) else f'Bar {i+1}',
                        'position': value_info.get('position'),
                        'metadata': {
                            'chart_type': chart_type,
                            'confidence': value_info.get('confidence', 0.5)
                        }
                    }
                    structured_data.append(entry)

            elif chart_type == 'pie_chart':
                segments = chart_data.get('segments', [])
                legend_labels = text_data.get('legend_labels', [])

                for i, segment in enumerate(segments):
                    entry = {
                        'type': 'pie_segment',
                        'index': i,
                        'value': segment.get('value', 0),
                        'percentage': segment.get('percentage', 0),
                        'label': legend_labels[i] if i < len(legend_labels) else f'Segment {i+1}',
                        'color': segment.get('color'),
                        'metadata': {
                            'chart_type': chart_type,
                            'angle': segment.get('angle', 0)
                        }
                    }
                    structured_data.append(entry)

            # Generic data entry for other chart types
            else:
                entry = {
                    'type': 'chart_summary',
                    'chart_type': chart_type,
                    'data_points': len(chart_data.get('values', [])),
                    'text_elements': len(text_data.get('x_labels', [])) + len(text_data.get('y_labels', [])),
                    'metadata': {
                        'confidence': parsing_result.get('metadata', {}).get('parsing_confidence', 0.0),
                        'extraction_method': 'automated'
                    }
                }
                structured_data.append(entry)

        except Exception as e:
            logger.warning(f"Failed to create structured data: {e}")

        return structured_data

    def _get_point_color(self, image: np.ndarray, point: Tuple[int, int]) -> Tuple[int, ...]:
        """Get color of point in image."""
        x, y = point
        if len(image.shape) == 3 and 0 <= y < image.shape[0] and 0 <= x < image.shape[1]:
            return tuple(image[y, x])
        return (0, 0, 0)  # Default black







