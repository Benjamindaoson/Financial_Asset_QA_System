"""
Chart Analyzer for GraphRAG.

This module provides chart and visualization analysis capabilities,
extracting structured data from charts and converting to graph representations.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class ChartAnalyzer:
    """
    Chart analyzer for extracting data from visualizations.

    Uses computer vision and deep learning to understand charts,
    extract data points, and convert to structured representations.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize chart analyzer.

        Args:
            model_path: Path to pre-trained chart analysis model
        """
        self.model_path = model_path

        # Chart type classification model (simplified)
        self.chart_types = [
            'bar_chart', 'line_chart', 'pie_chart', 'scatter_plot',
            'histogram', 'area_chart', 'box_plot', 'heatmap'
        ]

        # Color mapping for data series identification
        self.color_map = {
            'red': [255, 0, 0],
            'green': [0, 255, 0],
            'blue': [0, 0, 255],
            'yellow': [255, 255, 0],
            'purple': [128, 0, 128],
            'orange': [255, 165, 0],
            'black': [0, 0, 0],
            'gray': [128, 128, 128]
        }

        logger.info("Chart analyzer initialized")

    def analyze_chart(self, image: Union[str, Image.Image]) -> Dict[str, Any]:
        """
        Analyze a chart image and extract structured data.

        Args:
            image: Chart image path or PIL Image

        Returns:
            Chart analysis results
        """
        try:
            # Load image
            if isinstance(image, str):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            # Convert to OpenCV format
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            analysis = {
                "chart_type": self._classify_chart_type(cv_image),
                "title": self._extract_title(cv_image, pil_image),
                "axes": self._extract_axes(cv_image),
                "data_series": self._extract_data_series(cv_image),
                "legend": self._extract_legend(cv_image),
                "data_points": self._extract_data_points(cv_image),
                "confidence": 0.0,  # Would be calculated by ML model
                "metadata": {
                    "dimensions": pil_image.size,
                    "extraction_method": "cv_analysis"
                }
            }

            # Calculate overall confidence
            analysis["confidence"] = self._calculate_confidence(analysis)

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze chart: {e}")
            return {"error": str(e)}

    def _classify_chart_type(self, image: np.ndarray) -> str:
        """
        Classify chart type using computer vision heuristics.

        Args:
            image: OpenCV image array

        Returns:
            Chart type classification
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Analyze contour shapes and arrangements
        height, width = image.shape[:2]

        # Check for bar chart patterns (vertical rectangles)
        bar_count = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = h / max(w, 1)

            # Tall, thin rectangles suggest bars
            if aspect_ratio > 2 and w < width * 0.1:
                bar_count += 1

        if bar_count > 3:
            return "bar_chart"

        # Check for pie chart patterns (circular shapes)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20,
                                  param1=50, param2=30, minRadius=20, maxRadius=min(width, height)//2)

        if circles is not None and len(circles[0]) > 0:
            return "pie_chart"

        # Check for line patterns
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                               minLineLength=50, maxLineGap=10)

        if lines is not None and len(lines) > 5:
            # Check if lines are roughly horizontal/vertical (axes)
            horizontal_lines = sum(1 for line in lines if abs(line[0][1] - line[0][3]) < 10)
            vertical_lines = sum(1 for line in lines if abs(line[0][0] - line[0][2]) < 10)

            if horizontal_lines > 2 and vertical_lines > 2:
                return "line_chart"

        # Default classification
        return "unknown"

    def _extract_title(self, cv_image: np.ndarray, pil_image: Image.Image) -> Optional[str]:
        """
        Extract chart title using OCR and positioning heuristics.

        Args:
            cv_image: OpenCV image
            pil_image: PIL image for OCR

        Returns:
            Extracted title text
        """
        # Simple heuristic: text in top portion of image
        height, width = cv_image.shape[:2]
        top_region = pil_image.crop((0, 0, width, height // 5))

        # Would use OCR here - placeholder
        return "Chart Title (OCR Required)"

    def _extract_axes(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Extract chart axes information.

        Args:
            image: OpenCV image

        Returns:
            Axes information
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # Find lines that could be axes
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=50, maxLineGap=10)

        axes = {"x_axis": None, "y_axis": None, "labels": []}

        if lines is not None:
            height, width = image.shape[:2]

            for line in lines:
                x1, y1, x2, y2 = line[0]

                # Check for horizontal axis (bottom of chart)
                if abs(y1 - height) < 50 and abs(y2 - height) < 50 and abs(x2 - x1) > width * 0.5:
                    axes["x_axis"] = {"start": (x1, y1), "end": (x2, y2)}

                # Check for vertical axis (left side of chart)
                elif abs(x1 - 0) < 50 and abs(x2 - 0) < 50 and abs(y2 - y1) > height * 0.5:
                    axes["y_axis"] = {"start": (x1, y1), "end": (x2, y2)}

        return axes

    def _extract_data_series(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extract data series from chart.

        Args:
            image: OpenCV image

        Returns:
            List of data series
        """
        # Simplified data series extraction
        series = []

        # For different chart types, different extraction methods
        chart_type = self._classify_chart_type(image)

        if chart_type == "bar_chart":
            series = self._extract_bar_series(image)
        elif chart_type == "line_chart":
            series = self._extract_line_series(image)
        elif chart_type == "pie_chart":
            series = self._extract_pie_series(image)

        return series

    def _extract_bar_series(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract bar chart data series."""
        # Simplified bar extraction - would use more sophisticated CV
        return [
            {
                "name": "Series 1",
                "color": "blue",
                "values": [10, 20, 15, 25],  # Placeholder
                "positions": [(100, 200), (150, 180), (200, 190), (250, 175)]
            }
        ]

    def _extract_line_series(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract line chart data series."""
        # Simplified line extraction
        return [
            {
                "name": "Trend Line",
                "color": "red",
                "values": [5, 15, 25, 20, 30],
                "positions": [(50, 250), (100, 200), (150, 150), (200, 180), (250, 120)]
            }
        ]

    def _extract_pie_series(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract pie chart data series."""
        # Simplified pie extraction
        return [
            {"name": "Category A", "value": 40, "color": "red", "percentage": 40.0},
            {"name": "Category B", "value": 30, "color": "blue", "percentage": 30.0},
            {"name": "Category C", "value": 30, "color": "green", "percentage": 30.0}
        ]

    def _extract_legend(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Extract chart legend information.

        Args:
            image: OpenCV image

        Returns:
            Legend information
        """
        # Simplified legend detection - look for colored boxes with text
        return {
            "detected": True,
            "position": "bottom_right",  # Placeholder
            "items": [
                {"label": "Series 1", "color": "blue"},
                {"label": "Series 2", "color": "red"}
            ]
        }

    def _extract_data_points(self, image: np.ndarray) -> List[Dict[str, float]]:
        """
        Extract individual data points from chart.

        Args:
            image: OpenCV image

        Returns:
            List of data points with coordinates and values
        """
        # Simplified data point extraction
        points = []

        # This would use computer vision to detect and extract actual data points
        # For now, return placeholder data
        chart_type = self._classify_chart_type(image)

        if chart_type == "bar_chart":
            points = [
                {"x": 0, "y": 10, "value": 10, "series": "A"},
                {"x": 1, "y": 20, "value": 20, "series": "A"},
                {"x": 2, "y": 15, "value": 15, "series": "A"}
            ]
        elif chart_type == "line_chart":
            points = [
                {"x": 0, "y": 5, "value": 5, "series": "Line 1"},
                {"x": 1, "y": 15, "value": 15, "series": "Line 1"},
                {"x": 2, "y": 25, "value": 25, "series": "Line 1"}
            ]

        return points

    def _calculate_confidence(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall analysis confidence."""
        confidence = 0.0
        factors = 0

        # Chart type confidence
        if analysis["chart_type"] != "unknown":
            confidence += 0.4
        factors += 1

        # Axes detection confidence
        if analysis["axes"]["x_axis"] or analysis["axes"]["y_axis"]:
            confidence += 0.3
        factors += 1

        # Data series confidence
        if analysis["data_series"]:
            confidence += 0.3
        factors += 1

        return confidence / factors if factors > 0 else 0.0

    def convert_chart_to_graph(self, chart_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert chart analysis to graph-compatible format.

        Args:
            chart_analysis: Chart analysis results

        Returns:
            Graph representation of chart data
        """
        graph_format = {
            "chart_node": {
                "id": f"chart_{hash(str(chart_analysis)) % 1000000}",
                "type": "chart",
                "properties": {
                    "chart_type": chart_analysis["chart_type"],
                    "title": chart_analysis["title"],
                    "confidence": chart_analysis["confidence"]
                }
            },
            "data_nodes": [],
            "series_nodes": [],
            "relationships": []
        }

        # Create data point nodes
        for point in chart_analysis.get("data_points", []):
            data_node = {
                "id": f"data_point_{hash(str(point)) % 1000000}",
                "type": "data_point",
                "properties": {
                    "x": point["x"],
                    "y": point["y"],
                    "value": point["value"],
                    "series": point.get("series", "default")
                }
            }
            graph_format["data_nodes"].append(data_node)

            # Relationship: chart -> data_point
            graph_format["relationships"].append({
                "source": graph_format["chart_node"]["id"],
                "target": data_node["id"],
                "type": "contains_data",
                "properties": {"position": f"{point['x']},{point['y']}"}
            })

        # Create series nodes
        for series in chart_analysis.get("data_series", []):
            series_node = {
                "id": f"series_{hash(series.get('name', 'unnamed')) % 1000000}",
                "type": "data_series",
                "properties": {
                    "name": series.get("name", "Unnamed"),
                    "color": series.get("color", "unknown"),
                    "values": series.get("values", [])
                }
            }
            graph_format["series_nodes"].append(series_node)

            # Relationship: chart -> series
            graph_format["relationships"].append({
                "source": graph_format["chart_node"]["id"],
                "target": series_node["id"],
                "type": "has_series",
                "properties": {"color": series.get("color")}
            })

        return graph_format







