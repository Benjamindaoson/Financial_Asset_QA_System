"""
Advanced Image Processor for TrustRAG.
Enhanced OCR with preprocessing, quality assessment, and robust text extraction.
"""
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from trust_rag.config import get_config
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity, ChunkTier

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Advanced image preprocessing for OCR quality improvement.
    """

    def __init__(self):
        self.config = get_config().document_processing

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Apply multiple preprocessing techniques to improve OCR accuracy.
        """
        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        # Apply preprocessing pipeline
        processed = self._enhance_contrast(image)
        processed = self._reduce_noise(processed)
        processed = self._correct_skew(processed)
        processed = self._binarize(processed)

        return processed

    def _enhance_contrast(self, image: Image.Image) -> Image.Image:
        """Enhance image contrast."""
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(2.0)  # Increase contrast by 2x

    def _reduce_noise(self, image: Image.Image) -> Image.Image:
        """Reduce image noise."""
        # Apply median filter to reduce noise
        return image.filter(ImageFilter.MedianFilter(size=3))

    def _correct_skew(self, image: Image.Image) -> Image.Image:
        """Correct image skew/rotation."""
        # Simple skew detection and correction
        try:
            # Convert to grayscale for analysis
            gray = image.convert('L')

            # Find skew angle (simplified implementation)
            # In production, you might use more sophisticated algorithms
            skew_angle = self._detect_skew_angle(gray)

            if abs(skew_angle) > 0.5:  # Only correct if skew is significant
                return image.rotate(-skew_angle, expand=True)

        except Exception as e:
            logger.debug(f"Skew correction failed: {e}")

        return image

    def _detect_skew_angle(self, gray_image: Image.Image) -> float:
        """Detect skew angle in grayscale image."""
        # Simplified skew detection
        # This is a basic implementation - production systems might use
        # more sophisticated methods like projection profiles or Hough transform

        width, height = gray_image.size
        pixels = np.array(gray_image)

        # Find text lines by looking for horizontal projections
        horizontal_projection = np.sum(pixels < 128, axis=1)  # Dark pixels

        # Find peaks in projection (potential text lines)
        peaks = []
        threshold = np.mean(horizontal_projection) * 0.5

        for i in range(1, len(horizontal_projection) - 1):
            if (horizontal_projection[i] > threshold and
                horizontal_projection[i] > horizontal_projection[i-1] and
                horizontal_projection[i] > horizontal_projection[i+1]):
                peaks.append(i)

        if len(peaks) < 3:  # Not enough text lines to detect skew
            return 0.0

        # For this simplified version, assume no significant skew
        # A full implementation would analyze the angle of text lines
        return 0.0

    def _binarize(self, image: Image.Image) -> Image.Image:
        """Convert to binary image for better OCR."""
        # Convert to grayscale first
        gray = image.convert('L')

        # Apply adaptive thresholding
        pixels = np.array(gray)
        threshold = np.mean(pixels) * 0.8  # Adaptive threshold

        binary = pixels > threshold
        binary_image = Image.fromarray((binary * 255).astype(np.uint8))

        return binary_image


class OCRQualityAssessor:
    """
    Assess OCR quality and confidence.
    """

    def assess_quality(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess overall OCR quality from OCR data.
        """
        assessment = {
            'overall_confidence': 0.0,
            'text_density': 0.0,
            'character_count': 0,
            'word_count': 0,
            'line_count': 0,
            'quality_score': 0.0,
            'quality_level': 'unknown'
        }

        if not ocr_data or 'text' not in ocr_data:
            assessment['quality_level'] = 'failed'
            return assessment

        text = ocr_data['text']
        confidences = ocr_data.get('confidences', [])

        # Basic text metrics
        assessment['character_count'] = len(text)
        assessment['word_count'] = len(text.split())
        assessment['line_count'] = len(text.split('\n'))

        # Calculate text density (characters per area)
        if 'width' in ocr_data and 'height' in ocr_data:
            area = ocr_data['width'] * ocr_data['height']
            assessment['text_density'] = assessment['character_count'] / area if area > 0 else 0

        # Calculate confidence metrics
        if confidences:
            assessment['overall_confidence'] = sum(confidences) / len(confidences)

            # Quality scoring based on confidence distribution
            high_conf = sum(1 for c in confidences if c >= 80)
            medium_conf = sum(1 for c in confidences if 60 <= c < 80)
            low_conf = sum(1 for c in confidences if c < 60)

            total_chars = len(confidences)
            quality_score = (high_conf * 1.0 + medium_conf * 0.5 + low_conf * 0.1) / total_chars
            assessment['quality_score'] = quality_score

            # Quality level classification
            if quality_score >= 0.8:
                assessment['quality_level'] = 'high'
            elif quality_score >= 0.6:
                assessment['quality_level'] = 'medium'
            elif quality_score >= 0.4:
                assessment['quality_level'] = 'low'
            else:
                assessment['quality_level'] = 'very_low'
        else:
            # No confidence data available
            assessment['quality_level'] = 'unknown'

        return assessment

    def should_reject_ocr(self, quality_assessment: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determine if OCR result should be rejected based on quality.
        """
        quality_level = quality_assessment.get('quality_level', 'unknown')
        confidence = quality_assessment.get('overall_confidence', 0.0)
        char_count = quality_assessment.get('character_count', 0)

        # Rejection criteria
        if quality_level in ['failed', 'very_low']:
            return True, f"OCR quality too low: {quality_level}"

        if confidence < 30:  # Very low confidence
            return True, f"OCR confidence too low: {confidence:.1f}"

        if char_count < 10:  # Too little text extracted
            return True, f"Too little text extracted: {char_count} characters"

        return False, "OCR quality acceptable"


class AdvancedOCRProcessor:
    """
    Advanced OCR processor with preprocessing and quality assessment.
    """

    def __init__(self):
        self.config = get_config().document_processing
        self.preprocessor = ImagePreprocessor()
        self.quality_assessor = OCRQualityAssessor()

    def process_image(self, image_path: str, doc_id: Optional[str] = None) -> Tuple[List[Chunk], Dict[str, Any]]:
        """
        Process image with advanced OCR.
        """
        chunks = []
        metadata = {}

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Generate doc_id
        if not doc_id:
            filename = Path(image_path).name
            file_hash = hash(open(image_path, 'rb').read()) % 10000
            doc_id = f"{filename}_{file_hash}"

        try:
            # Load image
            original_image = Image.open(image_path)

            # Preprocess image
            processed_image = self.preprocessor.preprocess_image(original_image)

            # Perform OCR
            ocr_result = self._perform_ocr(processed_image)

            # Assess quality
            quality_assessment = self.quality_assessor.assess_quality(ocr_result)

            # Check if we should reject the OCR result
            should_reject, reject_reason = self.quality_assessor.should_reject_ocr(quality_assessment)

            if should_reject:
                logger.warning(f"Rejecting OCR result: {reject_reason}")

                # Create error chunk
                error_chunk = Chunk(
                    evidence_id=f"{doc_id}_ocr_rejected",
                    text=f"OCR extraction failed: {reject_reason}",
                    provenance=ChunkProvenance(
                        doc_id=doc_id,
                        source_path=image_path,
                        parser_name="advanced_ocr",
                        language=self.config.ocr_languages.split('+')[0],
                        modality="image",
                        block_index=0
                    ),
                    granularity=Granularity.ATOMIC,
                    tier=ChunkTier.MICRO,
                    metadata={
                        'ocr_failed': True,
                        'failure_reason': reject_reason,
                        'quality_assessment': quality_assessment
                    }
                )
                chunks.append(error_chunk)

            else:
                # Create successful OCR chunks
                ocr_chunks = self._create_ocr_chunks(ocr_result, quality_assessment, image_path, doc_id)
                chunks.extend(ocr_chunks)

            # Build metadata
            metadata = {
                'image_width': original_image.width,
                'image_height': original_image.height,
                'ocr_quality': quality_assessment,
                'preprocessing_applied': True,
                'ocr_engine': 'tesseract'
            }

            original_image.close()
            processed_image.close()

        except Exception as e:
            logger.error(f"Image processing failed: {e}")

            # Create error chunk
            error_chunk = Chunk(
                evidence_id=f"{doc_id}_processing_error",
                text=f"Image processing failed: {str(e)}",
                provenance=ChunkProvenance(
                    doc_id=doc_id,
                    source_path=image_path,
                    parser_name="advanced_ocr",
                    language="unknown",
                    modality="image",
                    block_index=0
                ),
                granularity=Granularity.ATOMIC,
                tier=ChunkTier.MICRO,
                metadata={'processing_error': str(e)}
            )
            chunks.append(error_chunk)

        return chunks, metadata

    def _perform_ocr(self, image: Image.Image) -> Dict[str, Any]:
        """Perform OCR on preprocessed image."""
        try:
            import pytesseract

            # Configure OCR
            custom_config = f'--oem 3 --psm 6 -l {self.config.ocr_languages}'

            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(
                image,
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )

            # Extract full text
            text = pytesseract.image_to_string(image, config=custom_config)

            # Get confidences for non-empty text regions
            confidences = []
            for conf, text_region in zip(ocr_data['conf'], ocr_data['text']):
                if text_region.strip() and conf != '-1':
                    confidences.append(int(conf))

            result = {
                'text': text,
                'confidences': confidences,
                'width': image.width,
                'height': image.height,
                'ocr_data': ocr_data
            }

            return result

        except ImportError:
            logger.error("OCR dependencies not installed. Install with: pip install pytesseract Pillow")
            return {'text': '', 'confidences': [], 'error': 'Dependencies not installed'}

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return {'text': '', 'confidences': [], 'error': str(e)}

    def _create_ocr_chunks(self, ocr_result: Dict[str, Any], quality: Dict[str, Any],
                          image_path: str, doc_id: str) -> List[Chunk]:
        """Create OCR chunks with quality metadata."""
        chunks = []

        text = ocr_result.get('text', '').strip()
        if not text:
            return chunks

        # Split text into reasonable chunks (by paragraphs or line breaks)
        text_chunks = self._split_text_into_chunks(text)

        for i, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue

            chunk_id = f"{doc_id}_ocr_{i}"
            evidence_id = f"ev_{chunk_id}"

            provenance = ChunkProvenance(
                doc_id=doc_id,
                source_path=image_path,
                parser_name="advanced_ocr",
                language=self.config.ocr_languages.split('+')[0],
                modality="image",
                block_index=i
            )

            # Determine confidence for this chunk
            # Use overall confidence as approximation
            chunk_confidence = quality.get('overall_confidence', 0.5)

            chunk = Chunk(
                evidence_id=evidence_id,
                text=chunk_text,
                provenance=provenance,
                granularity=Granularity.ATOMIC,
                tier=ChunkTier.MICRO,
                metadata={
                    'ocr_confidence': chunk_confidence,
                    'ocr_quality_level': quality.get('quality_level', 'unknown'),
                    'quality_score': quality.get('quality_score', 0.0),
                    'text_density': quality.get('text_density', 0.0),
                    'preprocessing_applied': True,
                    'chunk_index': i,
                    'image_width': ocr_result.get('width', 0),
                    'image_height': ocr_result.get('height', 0)
                }
            )

            chunks.append(chunk)

        return chunks

    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Split OCR text into reasonable chunks."""
        # Split by double newlines (paragraphs) first
        paragraphs = text.split('\n\n')

        chunks = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If paragraph is too long, split by single newlines
            if len(para) > 1000:
                lines = para.split('\n')
                current_chunk = ""

                for line in lines:
                    if len(current_chunk) + len(line) > 800:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line
                    else:
                        current_chunk += "\n" + line

                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                chunks.append(para)

        return chunks


class ImageEvidenceValidator:
    """
    Validate image evidence quality and provide recommendations.
    """

    def validate_image_evidence(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """Validate quality of image-derived evidence."""
        validation = {
            'total_chunks': len(chunks),
            'ocr_chunks': 0,
            'high_quality_chunks': 0,
            'medium_quality_chunks': 0,
            'low_quality_chunks': 0,
            'average_confidence': 0.0,
            'quality_distribution': {},
            'recommendations': []
        }

        confidences = []

        for chunk in chunks:
            if chunk.provenance.modality == 'image':
                validation['ocr_chunks'] += 1

                confidence = chunk.metadata.get('ocr_confidence', 0.0)
                confidences.append(confidence)

                quality_level = chunk.metadata.get('ocr_quality_level', 'unknown')

                if quality_level == 'high':
                    validation['high_quality_chunks'] += 1
                elif quality_level == 'medium':
                    validation['medium_quality_chunks'] += 1
                elif quality_level == 'low':
                    validation['low_quality_chunks'] += 1

                validation['quality_distribution'][quality_level] = \
                    validation['quality_distribution'].get(quality_level, 0) + 1

        if confidences:
            validation['average_confidence'] = sum(confidences) / len(confidences)

        # Generate recommendations
        if validation['average_confidence'] < 0.6:
            validation['recommendations'].append("Consider rescanning documents at higher resolution")

        if validation['low_quality_chunks'] > validation['ocr_chunks'] * 0.5:
            validation['recommendations'].append("High proportion of low-quality OCR - consider manual review")

        if validation['ocr_chunks'] == 0:
            validation['recommendations'].append("No OCR text extracted - verify image contains readable text")

        return validation

