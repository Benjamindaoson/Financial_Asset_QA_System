"""
Advanced Chart Parser for GraphRAG.

This module provides comprehensive chart parsing with DETR detection,
OCR processing, layout analysis, and multimodal fusion for complex charts.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import torch
from pathlib import Path

logger = logging.getLogger(__name__)


class AdvancedChartParser:
    """
    Advanced chart parser combining multiple AI models for comprehensive chart understanding.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize advanced chart parser.

        Args:
            config: Parser configuration
        """
        self.config = config or {}

        # Component configurations
        self.detr_config = self.config.get('detr', {})
        self.ocr_config = self.config.get('ocr', {})
        self.layout_config = self.config.get('layout', {})
        self.gnn_config = self.config.get('gnn', {})
        self.fusion_config = self.config.get('fusion', {})

        # Initialize components
        self.detr_detector = None
        self.ocr_processor = None
        self.layout_processor = None
        self.gnn_reasoner = None
        self.fusion_processor = None

        self._init_components()

        # Performance tracking
        self.parse_stats = {
            'total_parses': 0,
            'successful_parses': 0,
            'avg_parse_time': 0.0,
            'error_rate': 0.0
        }

        logger.info("Advanced Chart Parser initialized")

    def _init_components(self):
        """Initialize all parser components."""
        try:
            # Import and initialize components
            from .detr_detector import DETRChartDetector
            self.detr_detector = DETRChartDetector(self.detr_config)

            from .chart_ocr_processor import ChartOCRProcessor
            self.ocr_processor = ChartOCRProcessor(self.ocr_config)

            from .layoutlm_processor import LayoutLMProcessor
            self.layout_processor = LayoutLMProcessor(self.layout_config)

            from .gnn_chart_reasoner import GNNChartReasoner
            self.gnn_reasoner = GNNChartReasoner(self.gnn_config)

            from .multimodal_chart_fusion import MultimodalChartFusion
            self.fusion_processor = MultimodalChartFusion(self.fusion_config)

            logger.info("All chart parser components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize parser components: {e}")
            # Continue with available components

    def parse_chart_comprehensive(self, image: Union[str, Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Perform comprehensive chart parsing with all available components.

        Args:
            image: Chart image (file path, PIL Image, or numpy array)

        Returns:
            Comprehensive parsing results
        """
        import time
        start_time = time.time()

        self.parse_stats['total_parses'] += 1

        try:
            # Load and preprocess image
            processed_image, image_info = self._preprocess_image(image)

            # Step 1: DETR-based chart detection and classification
            detection_results = self._perform_detection(processed_image)

            # Step 2: OCR processing for text extraction
            ocr_results = self._perform_ocr(processed_image)

            # Step 3: Layout analysis with LayoutLM
            layout_results = self._perform_layout_analysis(processed_image, ocr_results)

            # Step 4: Element extraction and structuring
            elements = self._extract_chart_elements(detection_results, ocr_results, layout_results)

            # Step 5: Graph construction
            chart_graph = self._construct_chart_graph(elements)

            # Step 6: GNN reasoning
            reasoning_results = self._perform_reasoning(chart_graph)

            # Step 7: Multimodal fusion
            fusion_results = self._perform_fusion({
                'image': processed_image,
                'chart_elements': elements,
                'ocr_texts': ocr_results.get('texts', []),
                'detection_results': detection_results,
                'reasoning_results': reasoning_results
            })

            # Compile final results
            parse_time = time.time() - start_time
            results = self._compile_results(
                image_info, detection_results, ocr_results, layout_results,
                elements, chart_graph, reasoning_results, fusion_results, parse_time
            )

            self.parse_stats['successful_parses'] += 1
            self._update_parse_stats(parse_time)

            logger.info(f"Comprehensive chart parsing completed in {parse_time:.2f}s")

            return results

        except Exception as e:
            parse_time = time.time() - start_time
            self._update_parse_stats(parse_time)

            logger.error(f"Comprehensive chart parsing failed: {e}")

            return {
                'success': False,
                'error': str(e),
                'parse_time': parse_time,
                'image_info': image_info if 'image_info' in locals() else None
            }

    def _preprocess_image(self, image: Union[str, Image.Image, np.ndarray]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Preprocess input image."""
        try:
            # Load image
            if isinstance(image, str):
                pil_image = Image.open(image).convert('RGB')
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            elif isinstance(image, Image.Image):
                pil_image = image.convert('RGB')
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            elif isinstance(image, np.ndarray):
                cv_image = image.copy()
                if len(cv_image.shape) == 3 and cv_image.shape[2] == 3:
                    pil_image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
                else:
                    pil_image = Image.fromarray(cv_image)
            else:
                raise ValueError(f"Unsupported image type: {type(image)}")

            # Basic preprocessing
            # Resize if too large (keep aspect ratio)
            max_dimension = 2048
            height, width = cv_image.shape[:2]

            if max(height, width) > max_dimension:
                scale = max_dimension / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                cv_image = cv2.resize(cv_image, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # Enhance contrast
            lab = cv2.cvtColor(cv_image, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            cv_image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

            image_info = {
                'original_size': (width, height),
                'processed_size': cv_image.shape[:2],
                'channels': cv_image.shape[2] if len(cv_image.shape) > 2 else 1,
                'format': 'RGB' if len(cv_image.shape) == 3 else 'Grayscale'
            }

            return cv_image, image_info

        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            raise

    def _perform_detection(self, image: np.ndarray) -> Dict[str, Any]:
        """Perform chart detection using DETR."""
        if not self.detr_detector:
            return {'chart_type': 'unknown', 'confidence': 0.0, 'error': 'DETR detector not available'}

        try:
            return self.detr_detector.detect_chart_type(image)
        except Exception as e:
            logger.warning(f"DETR detection failed: {e}")
            return {'chart_type': 'unknown', 'confidence': 0.0, 'error': str(e)}

    def _perform_ocr(self, image: np.ndarray) -> Dict[str, Any]:
        """Perform OCR processing."""
        if not self.ocr_processor:
            return {'texts': [], 'error': 'OCR processor not available'}

        try:
            return self.ocr_processor.extract_text(image)
        except Exception as e:
            logger.warning(f"OCR processing failed: {e}")
            return {'texts': [], 'error': str(e)}

    def _perform_layout_analysis(self, image: np.ndarray, ocr_results: Dict[str, Any]) -> Dict[str, Any]:
        """Perform layout analysis using LayoutLM."""
        if not self.layout_processor:
            return {'layout_elements': [], 'error': 'Layout processor not available'}

        try:
            return self.layout_processor.analyze_layout(image, ocr_results)
        except Exception as e:
            logger.warning(f"Layout analysis failed: {e}")
            return {'layout_elements': [], 'error': str(e)}

    def _extract_chart_elements(self, detection_results: Dict[str, Any],
                               ocr_results: Dict[str, Any],
                               layout_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and structure chart elements."""
        elements = {
            'chart_type': detection_results.get('chart_type', 'unknown'),
            'data_points': [],
            'axes': [],
            'labels': [],
            'legend': [],
            'title': [],
            'grid_lines': [],
            'data_regions': []
        }

        try:
            # Extract from layout results
            layout_elements = layout_results.get('layout_elements', [])

            for element in layout_elements:
                element_type = element.get('type', 'unknown')
                bbox = element.get('bbox', [0, 0, 0, 0])
                text = element.get('text', '')
                confidence = element.get('confidence', 0.0)

                structured_element = {
                    'id': f"{element_type}_{len(elements[element_type])}",
                    'bbox': bbox,
                    'text': text,
                    'confidence': confidence,
                    'type': element_type
                }

                # Categorize elements
                if element_type in elements:
                    elements[element_type].append(structured_element)
                else:
                    # Add to appropriate category based on heuristics
                    if 'axis' in element_type.lower():
                        elements['axes'].append(structured_element)
                    elif 'label' in element_type.lower():
                        elements['labels'].append(structured_element)
                    elif 'legend' in element_type.lower():
                        elements['legend'].append(structured_element)
                    elif 'title' in element_type.lower():
                        elements['title'].append(structured_element)
                    else:
                        elements['data_points'].append(structured_element)

            # Extract data regions based on chart type
            elements['data_regions'] = self._identify_data_regions(elements)

        except Exception as e:
            logger.warning(f"Element extraction failed: {e}")

        return elements

    def _identify_data_regions(self, elements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify data-containing regions in the chart."""
        regions = []
        chart_type = elements.get('chart_type', 'unknown')

        try:
            # Get all element bounding boxes
            all_bboxes = []
            for element_list in elements.values():
                if isinstance(element_list, list):
                    for element in element_list:
                        if 'bbox' in element:
                            all_bboxes.append(element['bbox'])

            if not all_bboxes:
                return regions

            # Find the overall data area (excluding axes and labels)
            all_bboxes = np.array(all_bboxes)
            min_x, min_y = np.min(all_bboxes[:, [0, 1]], axis=0)
            max_x, max_y = np.max(all_bboxes[:, [2, 3]], axis=0)

            # Define data region based on chart type
            if chart_type in ['bar_chart', 'line_chart', 'area_chart']:
                # Main plotting area
                data_region = {
                    'bbox': [min_x, min_y, max_x, max_y],
                    'type': 'plot_area',
                    'confidence': 0.8
                }
                regions.append(data_region)

            elif chart_type == 'pie_chart':
                # Central region for pie charts
                center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
                radius = min(max_x - min_x, max_y - min_y) / 2
                data_region = {
                    'bbox': [center_x - radius, center_y - radius,
                            center_x + radius, center_y + radius],
                    'type': 'pie_area',
                    'confidence': 0.8
                }
                regions.append(data_region)

            elif chart_type in ['scatter_plot', 'bubble_chart']:
                # Entire area for scatter plots
                data_region = {
                    'bbox': [min_x, min_y, max_x, max_y],
                    'type': 'scatter_area',
                    'confidence': 0.8
                }
                regions.append(data_region)

        except Exception as e:
            logger.warning(f"Data region identification failed: {e}")

        return regions

    def _construct_chart_graph(self, elements: Dict[str, Any]) -> Any:
        """Construct graph representation of chart."""
        try:
            from .gnn_chart_reasoner import ChartGraphData

            nodes = []
            edges = []

            # Convert elements to nodes
            node_id = 0
            for element_type, element_list in elements.items():
                if isinstance(element_list, list):
                    for element in element_list:
                        node = {
                            'id': node_id,
                            'type': element_type,
                            'bbox': element.get('bbox', [0, 0, 0, 0]),
                            'text': element.get('text', ''),
                            'confidence': element.get('confidence', 0.0)
                        }

                        # Add type-specific attributes
                        if element_type == 'data_points':
                            node['value'] = element.get('value')

                        nodes.append(node)
                        node_id += 1

            # Create edges based on spatial relationships
            for i, node1 in enumerate(nodes):
                for j, node2 in enumerate(nodes):
                    if i != j:
                        relationship = self._determine_relationship(node1, node2)
                        if relationship:
                            edges.append((i, j, relationship))

            chart_graph = ChartGraphData(nodes, edges)
            return chart_graph

        except Exception as e:
            logger.warning(f"Graph construction failed: {e}")
            return None

    def _determine_relationship(self, node1: Dict[str, Any], node2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Determine relationship between two nodes."""
        bbox1 = node1.get('bbox', [0, 0, 0, 0])
        bbox2 = node2.get('bbox', [0, 0, 0, 0])

        # Calculate spatial relationships
        center1 = [(bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2]
        center2 = [(bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2]

        distance = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

        # Check for adjacency
        if distance < 50:  # Threshold for adjacency
            return {
                'type': 'adjacent',
                'distance': distance,
                'direction': self._calculate_direction(center1, center2)
            }

        # Check for containment
        if (bbox1[0] <= bbox2[0] and bbox1[1] <= bbox2[1] and
            bbox1[2] >= bbox2[2] and bbox1[3] >= bbox2[3]):
            return {'type': 'contains', 'distance': 0}

        return None

    def _calculate_direction(self, center1: List[float], center2: List[float]) -> str:
        """Calculate directional relationship."""
        dx = center2[0] - center1[0]
        dy = center2[1] - center1[1]

        if abs(dx) > abs(dy):
            return 'horizontal'
        else:
            return 'vertical'

    def _perform_reasoning(self, chart_graph: Any) -> Dict[str, Any]:
        """Perform GNN-based reasoning."""
        if not self.gnn_reasoner or not chart_graph:
            return {'reasoning_results': [], 'error': 'GNN reasoner not available'}

        try:
            # Perform multiple reasoning tasks
            tasks = ['relationship_prediction', 'anomaly_detection', 'trend_analysis']

            reasoning_results = {}
            for task in tasks:
                result = self.gnn_reasoner.reason_over_chart(chart_graph, task)
                reasoning_results[task] = result

            return reasoning_results

        except Exception as e:
            logger.warning(f"GNN reasoning failed: {e}")
            return {'reasoning_results': [], 'error': str(e)}

    def _perform_fusion(self, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform multimodal fusion."""
        if not self.fusion_processor:
            return {'fused_features': [], 'error': 'Fusion processor not available'}

        try:
            return self.fusion_processor.fuse_chart_modalities(chart_data)
        except Exception as e:
            logger.warning(f"Multimodal fusion failed: {e}")
            return {'fused_features': [], 'error': str(e)}

    def _compile_results(self, image_info: Dict[str, Any], detection_results: Dict[str, Any],
                        ocr_results: Dict[str, Any], layout_results: Dict[str, Any],
                        elements: Dict[str, Any], chart_graph: Any,
                        reasoning_results: Dict[str, Any], fusion_results: Dict[str, Any],
                        parse_time: float) -> Dict[str, Any]:
        """Compile comprehensive parsing results."""
        return {
            'success': True,
            'image_info': image_info,
            'chart_type': detection_results.get('chart_type', 'unknown'),
            'chart_confidence': detection_results.get('confidence', 0.0),
            'extracted_texts': ocr_results.get('texts', []),
            'chart_elements': elements,
            'layout_analysis': layout_results,
            'graph_constructed': chart_graph is not None,
            'reasoning_results': reasoning_results,
            'fusion_results': fusion_results,
            'complexity_score': self._calculate_complexity_score(elements),
            'parse_time': parse_time,
            'processing_pipeline': [
                'image_preprocessing',
                'chart_detection',
                'ocr_processing',
                'layout_analysis',
                'element_extraction',
                'graph_construction',
                'gnn_reasoning',
                'multimodal_fusion'
            ]
        }

    def _calculate_complexity_score(self, elements: Dict[str, Any]) -> float:
        """Calculate chart complexity score."""
        total_elements = sum(len(v) if isinstance(v, list) else 0 for v in elements.values())

        # Factors contributing to complexity
        chart_type = elements.get('chart_type', 'unknown')
        type_complexity = {
            'bar_chart': 0.3,
            'line_chart': 0.4,
            'pie_chart': 0.5,
            'scatter_plot': 0.6,
            'combo_chart': 0.8,
            'stacked_bar': 0.7,
            'multi_line': 0.7,
            'unknown': 0.5
        }

        base_complexity = type_complexity.get(chart_type, 0.5)
        element_complexity = min(total_elements / 50, 1.0)  # Normalize

        return (base_complexity + element_complexity) / 2

    def _update_parse_stats(self, parse_time: float):
        """Update parsing statistics."""
        current_avg = self.parse_stats['avg_parse_time']
        total_parses = self.parse_stats['total_parses']

        # Exponential moving average
        alpha = 0.1
        self.parse_stats['avg_parse_time'] = alpha * parse_time + (1 - alpha) * current_avg

        if total_parses > 0:
            self.parse_stats['error_rate'] = (total_parses - self.parse_stats['successful_parses']) / total_parses

    def get_parser_stats(self) -> Dict[str, Any]:
        """Get parser performance statistics."""
        return {
            'parse_stats': self.parse_stats,
            'component_status': {
                'detr_detector': self.detr_detector is not None,
                'ocr_processor': self.ocr_processor is not None,
                'layout_processor': self.layout_processor is not None,
                'gnn_reasoner': self.gnn_reasoner is not None,
                'fusion_processor': self.fusion_processor is not None
            },
            'supported_chart_types': [
                'bar_chart', 'line_chart', 'pie_chart', 'scatter_plot',
                'histogram', 'area_chart', 'box_plot', 'heatmap',
                'radar_chart', 'combo_chart', 'stacked_bar', 'multi_line'
            ]
        }

    def batch_parse(self, images: List[Union[str, Image.Image, np.ndarray]]) -> List[Dict[str, Any]]:
        """
        Parse multiple charts in batch.

        Args:
            images: List of chart images

        Returns:
            List of parsing results
        """
        results = []

        for image in images:
            try:
                result = self.parse_chart_comprehensive(image)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch parsing failed for image: {e}")
                results.append({
                    'success': False,
                    'error': str(e)
                })

        logger.info(f"Batch parsed {len(images)} charts")
        return results







