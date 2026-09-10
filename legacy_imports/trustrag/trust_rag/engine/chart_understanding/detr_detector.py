"""
DETR Chart Detector for GraphRAG.

This module uses DETR (DEtection TRansformer) for advanced chart detection
and localization in images and documents.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
from PIL import Image
import numpy as np
import cv2
from pathlib import Path

logger = logging.getLogger(__name__)


class DETRChartDetector:
    """
    DETR-based chart detection and classification system.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DETR chart detector.

        Args:
            config: Detection configuration
        """
        self.config = config or {}

        # Model configuration
        self.model_name = self.config.get('model_name', 'facebook/detr-resnet-50')
        self.confidence_threshold = self.config.get('confidence_threshold', 0.7)
        self.device = self.config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')

        # Chart categories for detection
        self.chart_categories = {
            0: 'bar_chart',
            1: 'line_chart',
            2: 'pie_chart',
            3: 'scatter_plot',
            4: 'histogram',
            5: 'area_chart',
            6: 'box_plot',
            7: 'heatmap',
            8: 'radar_chart',
            9: 'table',
            10: 'text_block'
        }

        # DETR model and processor
        self.model = None
        self.processor = None

        # Initialize model
        self._init_detr_model()

        logger.info("DETR chart detector initialized")

    def _init_detr_model(self):
        """Initialize DETR model for chart detection."""
        try:
            from transformers import DetrImageProcessor, DetrForObjectDetection

            # Load model and processor
            self.processor = DetrImageProcessor.from_pretrained(self.model_name)
            self.model = DetrForObjectDetection.from_pretrained(self.model_name)

            # Move to device
            self.model.to(self.device)
            self.model.eval()

            logger.info(f"Loaded DETR model: {self.model_name} on {self.device}")

        except ImportError:
            logger.warning("Transformers not available, DETR detection disabled")
        except Exception as e:
            logger.error(f"Failed to initialize DETR model: {e}")

    def detect_charts(self, image: Union[str, Path, Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Detect charts in an image using DETR.

        Args:
            image: Input image

        Returns:
            Detection results with chart locations and types
        """
        if not self.model or not self.processor:
            return {'error': 'DETR model not available'}

        try:
            # Prepare image
            pil_image = self._prepare_image(image)

            # Run detection
            inputs = self.processor(images=pil_image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Process results
            results = self.processor.post_process_object_detection(
                outputs, target_sizes=torch.tensor([pil_image.size[::-1]])
            )[0]

            # Extract chart detections
            detections = self._process_detections(results, pil_image.size)

            return {
                'detections': detections,
                'image_size': pil_image.size,
                'model': self.model_name,
                'confidence_threshold': self.confidence_threshold
            }

        except Exception as e:
            logger.error(f"Chart detection failed: {e}")
            return {'error': str(e), 'detections': []}

    def _prepare_image(self, image: Union[str, Path, Image.Image, np.ndarray]) -> Image.Image:
        """Prepare image for DETR processing."""
        if isinstance(image, (str, Path)):
            return Image.open(image).convert('RGB')
        elif isinstance(image, np.ndarray):
            if len(image.shape) == 2:  # Grayscale
                return Image.fromarray(image).convert('RGB')
            elif len(image.shape) == 3:
                if image.shape[2] == 1:  # Single channel
                    return Image.fromarray(image.squeeze(), mode='L').convert('RGB')
                else:  # RGB/BGR
                    return Image.fromarray(image).convert('RGB')
        elif isinstance(image, Image.Image):
            return image.convert('RGB')

        raise ValueError(f"Unsupported image type: {type(image)}")

    def _process_detections(self, results: Dict[str, torch.Tensor], image_size: Tuple[int, int]) -> List[Dict[str, Any]]:
        """Process DETR detection results into chart detections."""
        detections = []

        scores = results["scores"]
        labels = results["labels"]
        boxes = results["boxes"]

        # Filter by confidence
        keep = scores > self.confidence_threshold
        scores = scores[keep]
        labels = labels[keep]
        boxes = boxes[keep]

        # Convert to chart detections
        for score, label, box in zip(scores, labels, boxes):
            label_id = label.item()

            if label_id in self.chart_categories:
                chart_type = self.chart_categories[label_id]

                # Convert box coordinates
                x1, y1, x2, y2 = box.tolist()
                bbox = [int(x1), int(y1), int(x2), int(y2)]

                detection = {
                    'chart_type': chart_type,
                    'confidence': float(score.item()),
                    'bbox': bbox,
                    'area': (x2 - x1) * (y2 - y1),
                    'center': [(x1 + x2) / 2, (y1 + y2) / 2],
                    'label_id': label_id
                }

                detections.append(detection)

        # Sort by confidence
        detections.sort(key=lambda x: x['confidence'], reverse=True)

        return detections

    def detect_and_classify(self, image: Union[str, Path, Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Detect charts and provide detailed classification.

        Args:
            image: Input image

        Returns:
            Detailed detection and classification results
        """
        detection_result = self.detect_charts(image)

        if 'error' in detection_result:
            return detection_result

        detections = detection_result['detections']

        # Enhanced classification
        enhanced_detections = []
        for detection in detections:
            enhanced = self._enhance_detection(detection, image)
            enhanced_detections.append(enhanced)

        detection_result['detections'] = enhanced_detections
        detection_result['summary'] = self._create_detection_summary(enhanced_detections)

        return detection_result

    def _enhance_detection(self, detection: Dict[str, Any], image: Union[str, Path, Image.Image, np.ndarray]) -> Dict[str, Any]:
        """Enhance detection with additional features."""
        enhanced = detection.copy()

        # Extract region of interest
        bbox = detection['bbox']
        roi = self._extract_roi(image, bbox)

        if roi is not None:
            # Analyze chart complexity
            enhanced['complexity'] = self._analyze_complexity(roi)

            # Detect chart orientation
            enhanced['orientation'] = self._detect_orientation(roi)

            # Estimate data points
            enhanced['estimated_data_points'] = self._estimate_data_points(roi, detection['chart_type'])

            # Detect color scheme
            enhanced['color_scheme'] = self._analyze_color_scheme(roi)

        return enhanced

    def _extract_roi(self, image: Union[str, Path, Image.Image, np.ndarray], bbox: List[int]) -> Optional[np.ndarray]:
        """Extract region of interest from image."""
        try:
            pil_image = self._prepare_image(image)
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            x1, y1, x2, y2 = bbox
            roi = cv_image[y1:y2, x1:x2]

            return roi if roi.size > 0 else None

        except Exception as e:
            logger.warning(f"ROI extraction failed: {e}")
            return None

    def _analyze_complexity(self, roi: np.ndarray) -> str:
        """Analyze chart complexity."""
        if roi is None or roi.size == 0:
            return 'unknown'

        # Calculate edge density
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / roi.size

        # Calculate color diversity
        pixels = roi.reshape(-1, 3)
        unique_colors = len(np.unique(pixels, axis=0))
        color_diversity = unique_colors / len(pixels)

        # Determine complexity
        if edge_density > 0.1 and color_diversity > 0.1:
            return 'high'
        elif edge_density > 0.05 or color_diversity > 0.05:
            return 'medium'
        else:
            return 'low'

    def _detect_orientation(self, roi: np.ndarray) -> str:
        """Detect chart orientation."""
        if roi is None:
            return 'unknown'

        height, width = roi.shape[:2]

        if width > height * 1.5:
            return 'horizontal'
        elif height > width * 1.5:
            return 'vertical'
        else:
            return 'square'

    def _estimate_data_points(self, roi: np.ndarray, chart_type: str) -> int:
        """Estimate number of data points in chart."""
        if roi is None:
            return 0

        if chart_type in ['bar_chart', 'histogram']:
            # Count vertical lines (bars)
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            return len(contours)

        elif chart_type == 'line_chart':
            # Estimate based on line detection
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=20, maxLineGap=10)
            return len(lines[0]) if lines is not None else 0

        elif chart_type == 'scatter_plot':
            # Use corner detection
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            corners = cv2.goodFeaturesToTrack(gray, 100, 0.01, 10)
            return len(corners) if corners is not None else 0

        else:
            # Default estimation
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            return len(contours)

    def _analyze_color_scheme(self, roi: np.ndarray) -> Dict[str, Any]:
        """Analyze color scheme of the chart."""
        if roi is None:
            return {'type': 'unknown'}

        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Calculate dominant colors
        pixels = hsv.reshape(-1, 3)
        pixels = pixels[np.random.choice(len(pixels), min(1000, len(pixels)), replace=False)]

        # Simple color clustering (could use k-means for better results)
        colors = []
        for pixel in pixels:
            h, s, v = pixel
            if s > 50 and v > 50:  # Saturated and bright colors
                colors.append(pixel)

        if len(colors) < 10:
            return {'type': 'monochrome', 'colors': 1}

        # Estimate number of distinct colors
        unique_colors = len(np.unique(np.array(colors), axis=0))
        color_count = min(unique_colors, 10)  # Cap at 10

        return {
            'type': 'colorful' if color_count > 3 else 'moderate',
            'colors': color_count,
            'diversity': color_count / max(1, len(colors))
        }

    def _create_detection_summary(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary of detection results."""
        if not detections:
            return {'total_charts': 0}

        chart_types = {}
        confidences = []
        complexities = {'low': 0, 'medium': 0, 'high': 0, 'unknown': 0}

        for detection in detections:
            chart_type = detection['chart_type']
            chart_types[chart_type] = chart_types.get(chart_type, 0) + 1

            confidences.append(detection['confidence'])

            complexity = detection.get('complexity', 'unknown')
            complexities[complexity] += 1

        return {
            'total_charts': len(detections),
            'chart_types': chart_types,
            'avg_confidence': sum(confidences) / len(confidences),
            'complexity_distribution': complexities,
            'dominant_type': max(chart_types.items(), key=lambda x: x[1])[0] if chart_types else None
        }

    def batch_detect(self, images: List[Union[str, Path, Image.Image, np.ndarray]]) -> List[Dict[str, Any]]:
        """
        Detect charts in multiple images.

        Args:
            images: List of images

        Returns:
            List of detection results
        """
        results = []

        for image in images:
            try:
                result = self.detect_charts(image)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch detection failed: {e}")
                results.append({'error': str(e), 'detections': []})

        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the DETR model."""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'confidence_threshold': self.confidence_threshold,
            'chart_categories': self.chart_categories,
            'available': self.model is not None and self.processor is not None
        }

    def update_confidence_threshold(self, threshold: float):
        """
        Update confidence threshold for detections.

        Args:
            threshold: New confidence threshold (0.0 to 1.0)
        """
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Updated confidence threshold to {self.confidence_threshold}")

    def fine_tune_model(self, training_data: List[Dict[str, Any]]):
        """
        Fine-tune DETR model with custom chart data.

        Args:
            training_data: Training data with images and annotations
        """
        logger.info("Fine-tuning DETR model with custom data")
        # Implementation would require training pipeline
        # This is a placeholder for future enhancement
        pass
