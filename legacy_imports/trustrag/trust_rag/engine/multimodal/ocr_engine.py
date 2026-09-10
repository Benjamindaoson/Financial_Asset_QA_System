"""
OCR Engine for GraphRAG.

This module provides optical character recognition capabilities
for extracting text from images and documents.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from PIL import Image
import pytesseract
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class OCREngine:
    """
    OCR engine for text extraction from images and documents.

    Supports multiple OCR engines and provides text localization,
    confidence scoring, and layout analysis.
    """

    def __init__(self, tesseract_config: str = '--oem 3 --psm 6'):
        """
        Initialize OCR engine.

        Args:
            tesseract_config: Tesseract configuration string
        """
        self.tesseract_config = tesseract_config

        # OCR engines configuration
        self.engines = {
            'tesseract': self._tesseract_ocr,
            'paddle': self._paddle_ocr,  # Would integrate PaddleOCR
            'easyocr': self._easyocr_ocr  # Would integrate EasyOCR
        }

        self.primary_engine = 'tesseract'

        logger.info("OCR engine initialized")

    def extract_text(self, image: Union[str, Image.Image], engine: str = None) -> Dict[str, Any]:
        """
        Extract text from image using specified OCR engine.

        Args:
            image: Image path or PIL Image
            engine: OCR engine to use ('tesseract', 'paddle', 'easyocr')

        Returns:
            OCR results with text, confidence, and layout information
        """
        try:
            # Load image
            if isinstance(image, str):
                pil_image = Image.open(image).convert('RGB')
            else:
                pil_image = image.convert('RGB')

            # Convert to OpenCV format for preprocessing
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            # Preprocess image for better OCR
            processed_image = self._preprocess_image(cv_image)

            # Select OCR engine
            ocr_engine = engine or self.primary_engine
            if ocr_engine not in self.engines:
                logger.warning(f"Unknown OCR engine {ocr_engine}, using {self.primary_engine}")
                ocr_engine = self.primary_engine

            # Perform OCR
            ocr_function = self.engines[ocr_engine]
            results = ocr_function(processed_image, pil_image)

            # Post-process results
            results = self._post_process_results(results, processed_image)

            return results

        except Exception as e:
            logger.error(f"Failed to extract text from image: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "error": str(e),
                "regions": []
            }

    def _tesseract_ocr(self, cv_image: np.ndarray, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Perform OCR using Tesseract.

        Args:
            cv_image: OpenCV image array
            pil_image: PIL image for additional processing

        Returns:
            OCR results
        """
        # Get text with bounding boxes
        data = pytesseract.image_to_data(cv_image, config=self.tesseract_config, output_type=pytesseract.Output.DICT)

        # Extract text regions
        regions = []
        full_text = ""
        total_confidence = 0
        word_count = 0

        n_boxes = len(data['text'])
        for i in range(n_boxes):
            if int(data['conf'][i]) > 0:  # Filter out low confidence
                text = data['text'][i].strip()
                if text:
                    confidence = int(data['conf'][i]) / 100.0
                    bbox = {
                        'x': data['left'][i],
                        'y': data['top'][i],
                        'width': data['width'][i],
                        'height': data['height'][i]
                    }

                    regions.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': bbox,
                        'type': 'word'
                    })

                    full_text += text + " "
                    total_confidence += confidence
                    word_count += 1

        # Get full text without bounding boxes (higher accuracy)
        full_text_clean = pytesseract.image_to_string(cv_image, config=self.tesseract_config).strip()

        return {
            'text': full_text_clean,
            'confidence': total_confidence / max(word_count, 1),
            'regions': regions,
            'word_count': word_count,
            'engine': 'tesseract'
        }

    def _paddle_ocr(self, cv_image: np.ndarray, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Perform OCR using PaddleOCR (placeholder).

        Args:
            cv_image: OpenCV image array
            pil_image: PIL image

        Returns:
            OCR results
        """
        # Placeholder for PaddleOCR integration
        # Would import and use PaddleOCR here
        return {
            'text': 'PaddleOCR not implemented',
            'confidence': 0.0,
            'regions': [],
            'engine': 'paddle'
        }

    def _easyocr_ocr(self, cv_image: np.ndarray, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Perform OCR using EasyOCR (placeholder).

        Args:
            cv_image: OpenCV image array
            pil_image: PIL image

        Returns:
            OCR results
        """
        # Placeholder for EasyOCR integration
        return {
            'text': 'EasyOCR not implemented',
            'confidence': 0.0,
            'regions': [],
            'engine': 'easyocr'
        }

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.

        Args:
            image: OpenCV image array

        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Apply thresholding to get binary image
        _, threshold = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Apply morphological operations to clean up the image
        kernel = np.ones((1, 1), np.uint8)
        processed = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel)
        processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)

        # Resize image if too small (improve OCR accuracy)
        height, width = processed.shape
        if height < 100 or width < 100:
            scale_factor = max(100 / height, 100 / width)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        return processed

    def _post_process_results(self, results: Dict[str, Any], image: np.ndarray) -> Dict[str, Any]:
        """
        Post-process OCR results.

        Args:
            results: Raw OCR results
            image: Original image

        Returns:
            Post-processed results
        """
        # Clean up text
        if 'text' in results:
            results['text'] = self._clean_ocr_text(results['text'])

        # Filter low-confidence regions
        if 'regions' in results:
            results['regions'] = [
                region for region in results['regions']
                if region.get('confidence', 0) > 0.5
            ]

        # Add layout analysis
        results['layout'] = self._analyze_layout(results.get('regions', []), image)

        # Calculate overall quality metrics
        results['quality_metrics'] = self._calculate_quality_metrics(results)

        return results

    def _clean_ocr_text(self, text: str) -> str:
        """
        Clean up OCR text.

        Args:
            text: Raw OCR text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())

        # Fix common OCR errors
        corrections = {
            'l': '1',  # Common mistake
            'O': '0',  # Common mistake
            '|': '1',  # Common mistake
        }

        # Only apply corrections in numeric contexts
        import re
        for wrong, correct in corrections.items():
            text = re.sub(rf'\b\d*{re.escape(wrong)}\d*\b', lambda m: m.group().replace(wrong, correct), text)

        return text

    def _analyze_layout(self, regions: List[Dict[str, Any]], image: np.ndarray) -> Dict[str, Any]:
        """
        Analyze text layout in the image.

        Args:
            regions: Text regions from OCR
            image: Original image

        Returns:
            Layout analysis results
        """
        if not regions:
            return {"type": "unknown", "structure": "empty"}

        height, width = image.shape[:2]

        # Group regions into lines
        lines = self._group_regions_into_lines(regions)

        # Analyze layout patterns
        layout_info = {
            "line_count": len(lines),
            "avg_words_per_line": sum(len(line) for line in lines) / max(len(lines), 1),
            "has_columns": self._detect_columns(lines, width),
            "has_tables": self._detect_tables(lines),
            "text_density": len(regions) / (width * height / 10000),  # Regions per 100x100 pixels
            "alignment": self._detect_alignment(lines, width)
        }

        # Classify overall layout
        if layout_info["has_tables"]:
            layout_type = "table"
        elif layout_info["has_columns"]:
            layout_type = "multi_column"
        elif layout_info["line_count"] > 10:
            layout_type = "paragraph"
        else:
            layout_type = "title_header"

        layout_info["type"] = layout_type

        return layout_info

    def _group_regions_into_lines(self, regions: List[Dict[str, Any]], tolerance: int = 10) -> List[List[Dict[str, Any]]]:
        """
        Group text regions into lines based on vertical position.

        Args:
            regions: Text regions
            tolerance: Vertical tolerance for line grouping

        Returns:
            List of lines, each containing regions
        """
        if not regions:
            return []

        # Sort regions by vertical position
        sorted_regions = sorted(regions, key=lambda r: r['bbox']['y'])

        lines = []
        current_line = [sorted_regions[0]]

        for region in sorted_regions[1:]:
            # Check if region is on the same line as current line
            current_y = sum(r['bbox']['y'] for r in current_line) / len(current_line)
            region_y = region['bbox']['y']

            if abs(region_y - current_y) <= tolerance:
                current_line.append(region)
            else:
                # Sort current line by x position and add to lines
                current_line.sort(key=lambda r: r['bbox']['x'])
                lines.append(current_line)
                current_line = [region]

        # Add last line
        if current_line:
            current_line.sort(key=lambda r: r['bbox']['x'])
            lines.append(current_line)

        return lines

    def _detect_columns(self, lines: List[List[Dict[str, Any]]], image_width: int) -> bool:
        """
        Detect if text is arranged in columns.

        Args:
            lines: Text lines
            image_width: Image width

        Returns:
            True if columns detected
        """
        if len(lines) < 3:
            return False

        # Check if lines have consistent horizontal gaps (suggesting columns)
        column_gaps = []

        for line in lines:
            if len(line) > 1:
                x_positions = [r['bbox']['x'] for r in line]
                gaps = [x_positions[i+1] - x_positions[i] for i in range(len(x_positions)-1)]
                column_gaps.extend(gaps)

        if not column_gaps:
            return False

        # Check if gaps are consistent (low variance)
        avg_gap = sum(column_gaps) / len(column_gaps)
        variance = sum((gap - avg_gap) ** 2 for gap in column_gaps) / len(column_gaps)

        # If variance is low relative to average, likely columns
        return variance < (avg_gap * 0.5) and avg_gap > image_width * 0.1

    def _detect_tables(self, lines: List[List[Dict[str, Any]]]) -> bool:
        """
        Detect table-like structures.

        Args:
            lines: Text lines

        Returns:
            True if table detected
        """
        if len(lines) < 2:
            return False

        # Check for regular grid-like patterns
        # This is a simplified heuristic
        line_lengths = [len(line) for line in lines]

        # If most lines have similar number of elements, might be a table
        if len(set(line_lengths)) <= 2:  # Allow some variation
            avg_length = sum(line_lengths) / len(line_lengths)
            consistent_lines = sum(1 for length in line_lengths if abs(length - avg_length) <= 1)
            return consistent_lines / len(line_lengths) > 0.8

        return False

    def _detect_alignment(self, lines: List[List[Dict[str, Any]]], image_width: int) -> str:
        """
        Detect text alignment.

        Args:
            lines: Text lines
            image_width: Image width

        Returns:
            Alignment type
        """
        if not lines:
            return "unknown"

        alignments = []

        for line in lines:
            if not line:
                continue

            first_x = line[0]['bbox']['x']
            last_x = line[-1]['bbox']['x'] + line[-1]['bbox']['width']

            # Check left alignment
            if first_x < image_width * 0.1:
                alignments.append("left")
            # Check center alignment
            elif abs((first_x + last_x) / 2 - image_width / 2) < image_width * 0.1:
                alignments.append("center")
            # Check right alignment
            elif last_x > image_width * 0.9:
                alignments.append("right")

        if not alignments:
            return "unknown"

        # Return most common alignment
        from collections import Counter
        return Counter(alignments).most_common(1)[0][0]

    def _calculate_quality_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate OCR quality metrics.

        Args:
            results: OCR results

        Returns:
            Quality metrics
        """
        metrics = {
            "avg_confidence": results.get("confidence", 0.0),
            "text_length": len(results.get("text", "")),
            "region_count": len(results.get("regions", [])),
            "layout_complexity": results.get("layout", {}).get("line_count", 0)
        }

        # Calculate text density (characters per region)
        if metrics["region_count"] > 0:
            metrics["chars_per_region"] = metrics["text_length"] / metrics["region_count"]
        else:
            metrics["chars_per_region"] = 0

        # Overall quality score
        quality_score = (
            metrics["avg_confidence"] * 0.4 +
            min(metrics["chars_per_region"] / 20, 1.0) * 0.3 +
            (1.0 if metrics["region_count"] > 0 else 0.0) * 0.3
        )
        metrics["overall_quality"] = quality_score

        return metrics

    def extract_tables_from_image(self, image: Union[str, Image.Image]) -> List[Dict[str, Any]]:
        """
        Extract table structures from image.

        Args:
            image: Image path or PIL Image

        Returns:
            List of extracted tables
        """
        # This would integrate with table detection models
        # For now, return OCR results that might contain table data
        ocr_results = self.extract_text(image)

        tables = []

        # Simple heuristic: if layout suggests table, create table structure
        layout = ocr_results.get("layout", {})
        if layout.get("has_tables"):
            # Try to reconstruct table from OCR regions
            table_data = self._reconstruct_table_from_regions(ocr_results.get("regions", []))
            if table_data:
                tables.append(table_data)

        return tables

    def _reconstruct_table_from_regions(self, regions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Reconstruct table structure from OCR regions.

        Args:
            regions: OCR text regions

        Returns:
            Table data if reconstruction successful
        """
        # This is a simplified table reconstruction
        # In practice, would use more sophisticated algorithms

        if not regions:
            return None

        # Group regions into a grid-like structure
        # This is a placeholder implementation
        return {
            "table_id": f"ocr_table_{hash(str(regions)) % 10000}",
            "headers": ["Column 1", "Column 2"],  # Placeholder
            "rows": [["Data 1", "Data 2"]],  # Placeholder
            "confidence": 0.5
        }







