"""
LayoutLM Processor for GraphRAG.

This module uses LayoutLM models to understand document layout and extract
structured information from chart images and documents.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import numpy as np
from PIL import Image
from pathlib import Path

logger = logging.getLogger(__name__)


class LayoutLMProcessor:
    """
    LayoutLM-based processor for document layout understanding and information extraction.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize LayoutLM processor.

        Args:
            config: Processor configuration
        """
        self.config = config or {}

        # Model configuration
        self.model_name = self.config.get('model_name', 'microsoft/layoutlm-base-uncased')
        self.device = self.config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.max_seq_length = self.config.get('max_seq_length', 512)

        # Layout understanding settings
        self.confidence_threshold = self.config.get('confidence_threshold', 0.8)
        self.enable_fine_tuning = self.config.get('enable_fine_tuning', False)

        # LayoutLM model and components
        self.model = None
        self.processor = None
        self.tokenizer = None

        # Initialize model
        self._init_layoutlm_model()

        logger.info("LayoutLM processor initialized")

    def _init_layoutlm_model(self):
        """Initialize LayoutLM model for layout understanding."""
        try:
            from transformers import LayoutLMTokenizer, LayoutLMForTokenClassification
            from transformers import LayoutLMProcessor as LayoutLMProc

            # Load tokenizer and model
            self.tokenizer = LayoutLMTokenizer.from_pretrained(self.model_name)
            self.model = LayoutLMForTokenClassification.from_pretrained(
                self.model_name,
                num_labels=5  # BIO format: B-PER, I-PER, B-LOC, I-LOC, O
            )

            # Try to load processor (may not be available for all models)
            try:
                self.processor = LayoutLMProc.from_pretrained(self.model_name)
            except:
                self.processor = None
                logger.info("LayoutLMProcessor not available, using manual processing")

            # Move to device
            self.model.to(self.device)
            self.model.eval()

            logger.info(f"Loaded LayoutLM model: {self.model_name} on {self.device}")

        except ImportError:
            logger.warning("Transformers not available, LayoutLM processing disabled")
        except Exception as e:
            logger.error(f"Failed to initialize LayoutLM model: {e}")

    def analyze_layout(self, image: Union[str, Path, Image.Image, np.ndarray],
                      words: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze document layout and extract structured information.

        Args:
            image: Document or chart image
            words: Pre-extracted words with bounding boxes (optional)

        Returns:
            Layout analysis results
        """
        if not self.model or not self.tokenizer:
            return {'error': 'LayoutLM model not available'}

        try:
            # Prepare image and text data
            pil_image = self._prepare_image(image)
            encoding = self._prepare_layout_encoding(pil_image, words)

            if not encoding:
                return {'error': 'Failed to prepare layout encoding'}

            # Run layout analysis
            with torch.no_grad():
                outputs = self.model(**encoding)
                predictions = outputs.logits.argmax(-1)

            # Process predictions
            layout_entities = self._process_predictions(predictions, encoding)

            # Extract structured information
            structured_info = self._extract_structured_info(layout_entities, pil_image.size)

            return {
                'layout_entities': layout_entities,
                'structured_info': structured_info,
                'image_size': pil_image.size,
                'model_used': self.model_name,
                'confidence_score': self._calculate_layout_confidence(layout_entities)
            }

        except Exception as e:
            logger.error(f"Layout analysis failed: {e}")
            return {'error': str(e)}

    def _prepare_image(self, image: Union[str, Path, Image.Image, np.ndarray]) -> Image.Image:
        """Prepare image for LayoutLM processing."""
        if isinstance(image, (str, Path)):
            return Image.open(image).convert('RGB')
        elif isinstance(image, np.ndarray):
            return Image.fromarray(image).convert('RGB')
        elif isinstance(image, Image.Image):
            return image.convert('RGB')

        raise ValueError(f"Unsupported image type: {type(image)}")

    def _prepare_layout_encoding(self, image: Image.Image, words: List[Dict[str, Any]] = None):
        """Prepare encoding for LayoutLM with layout information."""
        try:
            if words is None:
                # Extract words using OCR if not provided
                words = self._extract_words_from_image(image)

            if not words:
                return None

            # Prepare input data
            input_ids = []
            bbox = []
            attention_mask = []

            # Add CLS token
            input_ids.append(self.tokenizer.cls_token_id)
            bbox.append([0, 0, 0, 0])  # CLS bbox
            attention_mask.append(1)

            # Process words
            for word_info in words[:self.max_seq_length - 2]:  # Reserve space for CLS and SEP
                word_tokens = self.tokenizer.tokenize(word_info['text'])

                # Add word tokens
                for token in word_tokens:
                    token_id = self.tokenizer.convert_tokens_to_ids(token)
                    input_ids.append(token_id)

                    # Use word bbox for all tokens of this word
                    bbox.append(word_info['bbox'])
                    attention_mask.append(1)

            # Add SEP token
            input_ids.append(self.tokenizer.sep_token_id)
            bbox.append([0, 0, 0, 0])  # SEP bbox
            attention_mask.append(1)

            # Pad to max length
            padding_length = self.max_seq_length - len(input_ids)
            input_ids.extend([self.tokenizer.pad_token_id] * padding_length)
            bbox.extend([[0, 0, 0, 0]] * padding_length)
            attention_mask.extend([0] * padding_length)

            # Convert to tensors
            encoding = {
                'input_ids': torch.tensor([input_ids], dtype=torch.long).to(self.device),
                'bbox': torch.tensor([bbox], dtype=torch.long).to(self.device),
                'attention_mask': torch.tensor([attention_mask], dtype=torch.long).to(self.device)
            }

            # Add image if processor is available
            if self.processor:
                image_encoding = self.processor(image, return_tensors="pt")
                encoding.update(image_encoding)

            return encoding

        except Exception as e:
            logger.error(f"Failed to prepare layout encoding: {e}")
            return None

    def _extract_words_from_image(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Extract words from image using OCR."""
        try:
            import pytesseract

            # Get OCR data
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT
            )

            words = []
            n_boxes = len(data['text'])

            for i in range(n_boxes):
                text = data['text'][i].strip()
                confidence = int(data['conf'][i])

                if text and confidence > 50:  # Filter low confidence
                    bbox = [
                        data['left'][i],
                        data['top'][i],
                        data['left'][i] + data['width'][i],
                        data['top'][i] + data['height'][i]
                    ]

                    words.append({
                        'text': text,
                        'bbox': bbox,
                        'confidence': confidence
                    })

            return words

        except ImportError:
            logger.warning("Tesseract not available for word extraction")
            return []
        except Exception as e:
            logger.error(f"Word extraction failed: {e}")
            return []

    def _process_predictions(self, predictions: torch.Tensor, encoding: Dict[str, torch.Tensor]) -> List[Dict[str, Any]]:
        """Process LayoutLM predictions into entities."""
        predictions = predictions[0]  # Remove batch dimension
        input_ids = encoding['input_ids'][0]

        entities = []
        current_entity = None

        # BIO tag mapping (simplified)
        id2label = {
            0: 'O',      # Outside
            1: 'B-TITLE',   # Beginning of Title
            2: 'I-TITLE',   # Inside Title
            3: 'B-LABEL',   # Beginning of Label
            4: 'I-LABEL'    # Inside Label
        }

        for i, (token_pred, token_id) in enumerate(zip(predictions, input_ids)):
            if token_id == self.tokenizer.pad_token_id:
                continue

            label = id2label.get(token_pred.item(), 'O')

            if label.startswith('B-'):
                # Start new entity
                if current_entity:
                    entities.append(current_entity)

                entity_type = label.split('-')[1]
                current_entity = {
                    'type': entity_type,
                    'tokens': [i],
                    'bbox': encoding['bbox'][0][i].tolist(),
                    'confidence': 1.0  # Simplified
                }

            elif label.startswith('I-') and current_entity:
                # Continue current entity
                current_entity['tokens'].append(i)
                # Update bbox to encompass all tokens
                current_bbox = encoding['bbox'][0][i].tolist()
                current_entity['bbox'] = [
                    min(current_entity['bbox'][0], current_bbox[0]),
                    min(current_entity['bbox'][1], current_bbox[1]),
                    max(current_entity['bbox'][2], current_bbox[2]),
                    max(current_entity['bbox'][3], current_bbox[3])
                ]

            elif current_entity:
                # End current entity
                entities.append(current_entity)
                current_entity = None

        # Add final entity if exists
        if current_entity:
            entities.append(current_entity)

        return entities

    def _extract_structured_info(self, layout_entities: List[Dict[str, Any]],
                               image_size: Tuple[int, int]) -> Dict[str, Any]:
        """Extract structured information from layout entities."""
        structured_info = {
            'title': None,
            'axis_labels': [],
            'legend_items': [],
            'data_regions': [],
            'annotations': []
        }

        for entity in layout_entities:
            entity_type = entity['type']
            bbox = entity['bbox']

            if entity_type == 'TITLE':
                # Title is typically at the top
                if bbox[1] < image_size[1] * 0.25:  # Top 25%
                    structured_info['title'] = entity

            elif entity_type == 'LABEL':
                # Determine if axis label based on position
                x_center = (bbox[0] + bbox[2]) / 2
                y_center = (bbox[1] + bbox[3]) / 2

                # Check if near edges (axis labels)
                near_left = bbox[0] < image_size[0] * 0.15
                near_right = bbox[2] > image_size[0] * 0.85
                near_bottom = bbox[3] > image_size[1] * 0.85
                near_top = bbox[1] < image_size[1] * 0.15

                if near_left or near_right or near_bottom or near_top:
                    structured_info['axis_labels'].append(entity)
                else:
                    # Could be legend or annotation
                    structured_info['annotations'].append(entity)

        # Identify data regions (areas not containing text entities)
        structured_info['data_regions'] = self._identify_data_regions(layout_entities, image_size)

        return structured_info

    def _identify_data_regions(self, entities: List[Dict[str, Any]],
                             image_size: Tuple[int, int]) -> List[Dict[str, Any]]:
        """Identify regions likely to contain chart data."""
        img_width, img_height = image_size

        # Define potential data regions (center area, avoiding text regions)
        candidate_regions = [
            {
                'bbox': [img_width * 0.1, img_height * 0.1, img_width * 0.9, img_height * 0.9],
                'type': 'main_plot_area',
                'confidence': 0.8
            }
        ]

        # Filter regions that don't overlap with text entities
        data_regions = []

        for region in candidate_regions:
            overlaps = False

            for entity in entities:
                if self._bboxes_overlap(region['bbox'], entity['bbox'], threshold=0.3):
                    overlaps = True
                    break

            if not overlaps:
                data_regions.append(region)

        return data_regions

    def _bboxes_overlap(self, bbox1: List[int], bbox2: List[int], threshold: float = 0.5) -> bool:
        """Check if bounding boxes overlap."""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2

        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i <= x1_i or y2_i <= y1_i:
            return False

        intersection_area = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)

        # IoU
        union_area = area1 + area2 - intersection_area
        iou = intersection_area / union_area if union_area > 0 else 0

        return iou > threshold

    def _calculate_layout_confidence(self, entities: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for layout analysis."""
        if not entities:
            return 0.0

        # Simple confidence based on number and quality of entities
        num_entities = len(entities)

        # Bonus for having title and axis labels
        has_title = any(e['type'] == 'TITLE' for e in entities)
        has_labels = any(e['type'] == 'LABEL' for e in entities)

        confidence = min(num_entities / 10, 1.0)  # Up to 10 entities

        if has_title:
            confidence += 0.2
        if has_labels:
            confidence += 0.1

        return min(confidence, 1.0)

    def analyze_chart_layout(self, image: Union[str, Path, Image.Image, np.ndarray],
                           chart_type: str = None) -> Dict[str, Any]:
        """
        Analyze chart layout with chart-type-specific processing.

        Args:
            image: Chart image
            chart_type: Type of chart for specialized analysis

        Returns:
            Chart layout analysis results
        """
        # Get basic layout analysis
        layout_result = self.analyze_layout(image)

        if 'error' in layout_result:
            return layout_result

        # Apply chart-specific enhancements
        enhanced_result = self._enhance_chart_layout(layout_result, chart_type)

        return enhanced_result

    def _enhance_chart_layout(self, layout_result: Dict[str, Any], chart_type: str = None) -> Dict[str, Any]:
        """Apply chart-type-specific layout enhancements."""
        if not chart_type:
            return layout_result

        structured_info = layout_result.get('structured_info', {})

        if chart_type in ['bar_chart', 'histogram']:
            # For bar charts, look for vertical alignment patterns
            structured_info = self._enhance_bar_chart_layout(structured_info, layout_result)

        elif chart_type in ['line_chart', 'area_chart']:
            # For line charts, look for connected data patterns
            structured_info = self._enhance_line_chart_layout(structured_info, layout_result)

        elif chart_type == 'pie_chart':
            # For pie charts, look for radial patterns
            structured_info = self._enhance_pie_chart_layout(structured_info, layout_result)

        elif chart_type == 'table':
            # For tables, look for grid patterns
            structured_info = self._enhance_table_layout(structured_info, layout_result)

        layout_result['structured_info'] = structured_info
        layout_result['chart_type'] = chart_type

        return layout_result

    def _enhance_bar_chart_layout(self, structured_info: Dict[str, Any], layout_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance layout analysis for bar charts."""
        # Add bar group detection logic
        structured_info['bar_groups'] = []  # Would implement bar group detection
        return structured_info

    def _enhance_line_chart_layout(self, structured_info: Dict[str, Any], layout_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance layout analysis for line charts."""
        # Add line series detection logic
        structured_info['line_series'] = []  # Would implement line series detection
        return structured_info

    def _enhance_pie_chart_layout(self, structured_info: Dict[str, Any], layout_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance layout analysis for pie charts."""
        # Add pie segment detection logic
        structured_info['pie_segments'] = []  # Would implement pie segment detection
        return structured_info

    def _enhance_table_layout(self, structured_info: Dict[str, Any], layout_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance layout analysis for tables."""
        # Add table structure detection logic
        structured_info['table_structure'] = {
            'rows': 0,
            'columns': 0,
            'headers': []
        }
        return structured_info

    def extract_chart_metadata(self, layout_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract high-level metadata from chart layout analysis.

        Args:
            layout_result: Layout analysis result

        Returns:
            Chart metadata
        """
        metadata = {
            'has_title': False,
            'num_axis_labels': 0,
            'num_data_regions': 0,
            'layout_complexity': 'simple',
            'text_density': 0.0
        }

        structured_info = layout_result.get('structured_info', {})

        # Check for title
        metadata['has_title'] = structured_info.get('title') is not None

        # Count axis labels
        metadata['num_axis_labels'] = len(structured_info.get('axis_labels', []))

        # Count data regions
        metadata['num_data_regions'] = len(structured_info.get('data_regions', []))

        # Determine complexity
        total_elements = (
            metadata['num_axis_labels'] +
            len(structured_info.get('legend_items', [])) +
            len(structured_info.get('annotations', []))
        )

        if total_elements > 10:
            metadata['layout_complexity'] = 'high'
        elif total_elements > 5:
            metadata['layout_complexity'] = 'medium'
        else:
            metadata['layout_complexity'] = 'simple'

        # Calculate text density
        entities = layout_result.get('layout_entities', [])
        if entities:
            total_text_area = sum(
                (e['bbox'][2] - e['bbox'][0]) * (e['bbox'][3] - e['bbox'][1])
                for e in entities
            )
            image_area = layout_result.get('image_size', (1, 1))[0] * layout_result.get('image_size', (1, 1))[1]
            metadata['text_density'] = total_text_area / image_area if image_area > 0 else 0.0

        return metadata

    def get_processor_info(self) -> Dict[str, Any]:
        """Get information about the LayoutLM processor."""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'max_seq_length': self.max_seq_length,
            'confidence_threshold': self.confidence_threshold,
            'available': self.model is not None and self.tokenizer is not None,
            'processor_available': self.processor is not None
        }
