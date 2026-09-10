"""
Chart OCR Processor for GraphRAG.

This module provides specialized OCR capabilities for extracting text from charts,
optimized for chart-specific text recognition including titles, labels, and legends.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import pytesseract
import torch
from pathlib import Path

logger = logging.getLogger(__name__)


class ChartOCRProcessor:
    """
    Advanced OCR processor specialized for chart text extraction.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Chart OCR processor.

        Args:
            config: OCR configuration
        """
        self.config = config or {}

        # OCR configuration
        self.lang = self.config.get('lang', 'eng')
        self.psm_mode = self.config.get('psm_mode', 6)  # Uniform block of text
        self.oem_mode = self.config.get('oem_mode', 3)  # Default OCR Engine Mode

        # Chart-specific settings
        self.enable_preprocessing = self.config.get('enable_preprocessing', True)
        self.text_min_confidence = self.config.get('text_min_confidence', 60)
        self.enable_spell_check = self.config.get('enable_spell_check', True)

        # Text categories for chart elements
        self.text_categories = {
            'title': self._is_title_text,
            'axis_label': self._is_axis_label,
            'legend': self._is_legend_text,
            'data_label': self._is_data_label,
            'annotation': self._is_annotation
        }

        # Initialize OCR models
        self._init_ocr_models()

        logger.info("Chart OCR processor initialized")

    def _init_ocr_models(self):
        """Initialize OCR models and check availability."""
        try:
            # Check Tesseract availability
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")

        # Check for advanced OCR models
        self.tr_ocr_available = self._check_tr_ocr()
        self.easy_ocr_available = self._check_easy_ocr()

    def _check_tr_ocr(self) -> bool:
        """Check if TrOCR (Transformer OCR) is available."""
        try:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            return True
        except ImportError:
            return False

    def _check_easy_ocr(self) -> bool:
        """Check if EasyOCR is available."""
        try:
            import easyocr
            return True
        except ImportError:
            return False

    def extract_chart_text(self, image: Union[str, Path, Image.Image, np.ndarray],
                          chart_type: str = None) -> Dict[str, Any]:
        """
        Extract text from chart image.

        Args:
            image: Chart image
            chart_type: Type of chart for specialized processing

        Returns:
            Extracted text with categorization and metadata
        """
        try:
            # Prepare image
            pil_image = self._prepare_image(image)

            # Apply chart-specific preprocessing
            processed_image = self._preprocess_chart_image(pil_image, chart_type)

            # Extract text using multiple OCR engines
            ocr_results = self._multi_engine_ocr(processed_image)

            # Categorize extracted text
            categorized_text = self._categorize_text(ocr_results, processed_image.size, chart_type)

            # Post-process and validate
            final_results = self._post_process_results(categorized_text, processed_image)

            return {
                'text_elements': final_results,
                'image_size': processed_image.size,
                'chart_type': chart_type,
                'ocr_engines_used': list(ocr_results.keys()),
                'confidence_score': self._calculate_overall_confidence(final_results)
            }

        except Exception as e:
            logger.error(f"Chart text extraction failed: {e}")
            return {'error': str(e), 'text_elements': []}

    def _prepare_image(self, image: Union[str, Path, Image.Image, np.ndarray]) -> Image.Image:
        """Prepare image for OCR processing."""
        if isinstance(image, (str, Path)):
            return Image.open(image).convert('RGB')
        elif isinstance(image, np.ndarray):
            return Image.fromarray(image).convert('RGB')
        elif isinstance(image, Image.Image):
            return image.convert('RGB')

        raise ValueError(f"Unsupported image type: {type(image)}")

    def _preprocess_chart_image(self, image: Image.Image, chart_type: str = None) -> Image.Image:
        """Apply chart-specific image preprocessing."""
        if not self.enable_preprocessing:
            return image

        # Convert to OpenCV format
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Apply preprocessing based on chart type
        if chart_type:
            cv_image = self._apply_chart_specific_preprocessing(cv_image, chart_type)
        else:
            cv_image = self._apply_general_preprocessing(cv_image)

        # Convert back to PIL
        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))

    def _apply_general_preprocessing(self, image: np.ndarray) -> np.ndarray:
        """Apply general image preprocessing for OCR."""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Morphological operations to clean up text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def _apply_chart_specific_preprocessing(self, image: np.ndarray, chart_type: str) -> np.ndarray:
        """Apply chart-type-specific preprocessing."""
        # Start with general preprocessing
        processed = self._apply_general_preprocessing(image)

        if chart_type in ['bar_chart', 'histogram']:
            # Enhance vertical lines (bars)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
            processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)

        elif chart_type in ['line_chart', 'area_chart']:
            # Enhance horizontal elements
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
            processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)

        elif chart_type == 'pie_chart':
            # Enhance circular elements
            processed = cv2.medianBlur(processed, 3)

        elif chart_type == 'table':
            # Enhance grid lines
            kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (2, 2))
            processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)

        return processed

    def _multi_engine_ocr(self, image: Image.Image) -> Dict[str, List[Dict[str, Any]]]:
        """Run OCR using multiple engines for better accuracy."""
        results = {}

        # Tesseract OCR
        tesseract_results = self._run_tesseract_ocr(image)
        if tesseract_results:
            results['tesseract'] = tesseract_results

        # TrOCR (if available)
        if self.tr_ocr_available:
            trocr_results = self._run_trocr_ocr(image)
            if trocr_results:
                results['trocr'] = trocr_results

        # EasyOCR (if available)
        if self.easy_ocr_available:
            easyocr_results = self._run_easyocr_ocr(image)
            if easyocr_results:
                results['easyocr'] = easyocr_results

        return results

    def _run_tesseract_ocr(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Run Tesseract OCR on image."""
        try:
            # Configure Tesseract
            custom_config = f'--oem {self.oem_mode} --psm {self.psm_mode}'

            # Get detailed OCR data
            data = pytesseract.image_to_data(
                image, lang=self.lang, config=custom_config, output_type=pytesseract.Output.DICT
            )

            results = []
            n_boxes = len(data['text'])

            for i in range(n_boxes):
                confidence = int(data['conf'][i])
                if confidence > self.text_min_confidence:
                    text = data['text'][i].strip()
                    if text:
                        results.append({
                            'text': text,
                            'bbox': [
                                data['left'][i],
                                data['top'][i],
                                data['left'][i] + data['width'][i],
                                data['top'][i] + data['height'][i]
                            ],
                            'confidence': confidence,
                            'font_size': data['height'][i],
                            'engine': 'tesseract'
                        })

            return results

        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            return []

    def _run_trocr_ocr(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Run TrOCR on image."""
        try:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            # Load model (cached)
            if not hasattr(self, '_trocr_model'):
                self._trocr_processor = TrOCRProcessor.from_pretrained('microsoft/trocr-base-printed')
                self._trocr_model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-base-printed')

            # Process image
            pixel_values = self._trocr_processor(image, return_tensors="pt").pixel_values

            # Generate text
            generated_ids = self._trocr_model.generate(pixel_values)
            generated_text = self._trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            if generated_text.strip():
                return [{
                    'text': generated_text.strip(),
                    'bbox': [0, 0, image.size[0], image.size[1]],  # Full image
                    'confidence': 85,  # Estimated confidence
                    'engine': 'trocr'
                }]

            return []

        except Exception as e:
            logger.warning(f"TrOCR failed: {e}")
            return []

    def _run_easyocr_ocr(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Run EasyOCR on image."""
        try:
            import easyocr

            # Initialize reader (cached)
            if not hasattr(self, '_easyocr_reader'):
                self._easyocr_reader = easyocr.Reader([self.lang.split('+')[0]])  # Primary language only

            # Convert PIL to numpy array
            img_array = np.array(image)

            # Run OCR
            results = self._easyocr_reader.readtext(img_array)

            ocr_results = []
            for (bbox, text, confidence) in results:
                if confidence > (self.text_min_confidence / 100.0):  # Convert to 0-1 scale
                    ocr_results.append({
                        'text': text.strip(),
                        'bbox': [int(coord) for coord in bbox.flatten()[:4]],  # Take first 4 coords
                        'confidence': int(confidence * 100),
                        'engine': 'easyocr'
                    })

            return ocr_results

        except Exception as e:
            logger.warning(f"EasyOCR failed: {e}")
            return []

    def _categorize_text(self, ocr_results: Dict[str, List[Dict[str, Any]]],
                        image_size: Tuple[int, int], chart_type: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize extracted text into chart elements."""
        categorized = {category: [] for category in self.text_categories.keys()}
        categorized['unknown'] = []

        # Collect all text elements
        all_texts = []
        for engine_results in ocr_results.values():
            all_texts.extend(engine_results)

        # Remove duplicates and merge overlapping text
        merged_texts = self._merge_overlapping_text(all_texts)

        # Categorize each text element
        for text_element in merged_texts:
            category = self._categorize_single_text(text_element, image_size, chart_type)
            categorized[category].append(text_element)

        return categorized

    def _merge_overlapping_text(self, text_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge overlapping or duplicate text elements."""
        if len(text_elements) <= 1:
            return text_elements

        merged = []

        # Sort by confidence (highest first)
        sorted_texts = sorted(text_elements, key=lambda x: x['confidence'], reverse=True)

        for text_elem in sorted_texts:
            # Check if overlaps with existing merged elements
            overlaps = False
            for merged_elem in merged:
                if self._bboxes_overlap(text_elem['bbox'], merged_elem['bbox']):
                    # Keep the higher confidence version
                    if text_elem['confidence'] > merged_elem['confidence']:
                        merged.remove(merged_elem)
                        merged.append(text_elem)
                    overlaps = True
                    break

            if not overlaps:
                merged.append(text_elem)

        return merged

    def _bboxes_overlap(self, bbox1: List[int], bbox2: List[int], threshold: float = 0.5) -> bool:
        """Check if two bounding boxes overlap significantly."""
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

        # Calculate areas
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)

        # Calculate IoU (Intersection over Union)
        union_area = area1 + area2 - intersection_area
        iou = intersection_area / union_area if union_area > 0 else 0

        return iou > threshold

    def _categorize_single_text(self, text_element: Dict[str, Any],
                               image_size: Tuple[int, int], chart_type: str = None) -> str:
        """Categorize a single text element."""
        for category, validator_func in self.text_categories.items():
            if validator_func(text_element, image_size, chart_type):
                return category

        return 'unknown'

    def _is_title_text(self, text_elem: Dict[str, Any], image_size: Tuple[int, int], chart_type: str = None) -> bool:
        """Check if text is likely a chart title."""
        bbox = text_elem['bbox']
        img_width, img_height = image_size

        # Title is typically at the top center
        y_position = (bbox[1] + bbox[3]) / 2  # Center Y
        x_position = (bbox[0] + bbox[2]) / 2  # Center X

        # Title criteria
        is_at_top = y_position < img_height * 0.25
        is_centered = abs(x_position - img_width / 2) < img_width * 0.3
        is_large_text = text_elem.get('font_size', 20) > 16

        return is_at_top and (is_centered or is_large_text)

    def _is_axis_label(self, text_elem: Dict[str, Any], image_size: Tuple[int, int], chart_type: str = None) -> bool:
        """Check if text is likely an axis label."""
        bbox = text_elem['bbox']
        img_width, img_height = image_size

        # Axis labels are typically at edges
        x1, y1, x2, y2 = bbox

        # Check if near edges
        near_left = x1 < img_width * 0.15
        near_right = x2 > img_width * 0.85
        near_bottom = y2 > img_height * 0.85
        near_top = y1 < img_height * 0.15

        return near_left or near_right or near_bottom or near_top

    def _is_legend_text(self, text_elem: Dict[str, Any], image_size: Tuple[int, int], chart_type: str = None) -> bool:
        """Check if text is likely legend text."""
        bbox = text_elem['bbox']
        img_width, img_height = image_size

        # Legend is typically on the side or bottom right
        x1, y1, x2, y2 = bbox

        # Check if in corner regions
        in_bottom_right = x1 > img_width * 0.6 and y1 > img_height * 0.6
        in_top_right = x1 > img_width * 0.6 and y2 < img_height * 0.4

        return in_bottom_right or in_top_right

    def _is_data_label(self, text_elem: Dict[str, Any], image_size: Tuple[int, int], chart_type: str = None) -> bool:
        """Check if text is likely a data label."""
        # Data labels are typically numbers or short text near data points
        text = text_elem['text'].strip()

        # Check if it's numeric or short
        is_numeric = text.replace('.', '').replace(',', '').replace('%', '').isdigit()
        is_short = len(text) <= 10

        return is_numeric or is_short

    def _is_annotation(self, text_elem: Dict[str, Any], image_size: Tuple[int, int], chart_type: str = None) -> bool:
        """Check if text is likely an annotation."""
        # Annotations are typically longer text elements
        text = text_elem['text'].strip()
        return len(text) > 20

    def _post_process_results(self, categorized_text: Dict[str, List[Dict[str, Any]]],
                            image: Image.Image) -> Dict[str, List[Dict[str, Any]]]:
        """Post-process and validate categorized text results."""
        processed = {}

        for category, texts in categorized_text.items():
            if not texts:
                processed[category] = []
                continue

            # Apply spell checking if enabled
            if self.enable_spell_check:
                texts = self._apply_spell_check(texts)

            # Sort by confidence
            texts.sort(key=lambda x: x['confidence'], reverse=True)

            processed[category] = texts

        return processed

    def _apply_spell_check(self, text_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply spell checking to text elements."""
        try:
            from spellchecker import SpellChecker

            if not hasattr(self, '_spell_checker'):
                self._spell_checker = SpellChecker()

            corrected_elements = []

            for elem in text_elements:
                text = elem['text']
                words = text.split()

                corrected_words = []
                for word in words:
                    if word.lower() in self._spell_checker:
                        corrected_words.append(word)
                    else:
                        # Find correction
                        correction = self._spell_checker.correction(word.lower())
                        corrected_words.append(correction if correction else word)

                elem['text'] = ' '.join(corrected_words)
                elem['spell_checked'] = True
                corrected_elements.append(elem)

            return corrected_elements

        except ImportError:
            logger.debug("Spell checker not available")
            return text_elements
        except Exception as e:
            logger.warning(f"Spell check failed: {e}")
            return text_elements

    def _calculate_overall_confidence(self, text_elements: Dict[str, List[Dict[str, Any]]]) -> float:
        """Calculate overall confidence score for extracted text."""
        all_confidences = []

        for texts in text_elements.values():
            all_confidences.extend([elem['confidence'] for elem in texts])

        if not all_confidences:
            return 0.0

        return sum(all_confidences) / len(all_confidences)

    def batch_extract_text(self, images: List[Union[str, Path, Image.Image, np.ndarray]],
                          chart_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        Extract text from multiple chart images.

        Args:
            images: List of chart images
            chart_types: Corresponding chart types (optional)

        Returns:
            List of extraction results
        """
        results = []

        for i, image in enumerate(images):
            chart_type = chart_types[i] if chart_types and i < len(chart_types) else None

            try:
                result = self.extract_chart_text(image, chart_type)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch text extraction failed for image {i}: {e}")
                results.append({'error': str(e), 'text_elements': []})

        return results

    def get_processor_info(self) -> Dict[str, Any]:
        """Get information about the OCR processor."""
        return {
            'lang': self.lang,
            'psm_mode': self.psm_mode,
            'oem_mode': self.oem_mode,
            'min_confidence': self.text_min_confidence,
            'preprocessing_enabled': self.enable_preprocessing,
            'spell_check_enabled': self.enable_spell_check,
            'engines_available': {
                'tesseract': True,  # Always available if installed
                'trocr': self.tr_ocr_available,
                'easyocr': self.easy_ocr_available
            },
            'text_categories': list(self.text_categories.keys())
        }
