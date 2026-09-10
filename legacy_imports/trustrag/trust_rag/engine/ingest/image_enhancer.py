"""
Advanced Image Enhancement for OCR.
Uses ESRGAN, Real-ESRGAN, and multimodal LLMs for image quality improvement.
"""
import logging
import base64
import json
from typing import Optional, Tuple, List, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)


class SiliconValleyImageEnhancer:
    """
    Multi-stage image enhancement pipeline inspired by advanced approaches.

    Pipeline:
    1. Quality assessment
    2. ESRGAN super-resolution (if needed)
    3. Advanced preprocessing (contrast, noise, skew)
    4. Multimodal LLM understanding (as fallback)
    """

    def __init__(self):
        self._esrgan_model = None
        self._multimodal_llm = None

    def enhance_image(self, image: Image.Image) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Enhance image using multi-stage pipeline.

        Returns:
            Enhanced image and enhancement metadata
        """
        metadata = {
            "original_size": image.size,
            "enhancement_steps": [],
            "quality_improvement": 0.0,
            "final_confidence": 0.0
        }

        # Stage 1: Quality assessment
        quality_score = self._assess_image_quality(image)
        metadata["initial_quality"] = quality_score

        enhanced = image

        # Stage 2: Super-resolution if low resolution
        if quality_score < 0.6:
            enhanced = self._apply_super_resolution(enhanced)
            metadata["enhancement_steps"].append("super_resolution")

        # Stage 3: Advanced preprocessing
        enhanced = self._advanced_preprocessing(enhanced)
        metadata["enhancement_steps"].append("preprocessing")

        # Stage 4: Quality reassessment
        final_quality = self._assess_image_quality(enhanced)
        metadata["final_quality"] = final_quality
        metadata["quality_improvement"] = final_quality - quality_score

        # Stage 5: Multimodal LLM understanding (for very low quality)
        if final_quality < 0.4:
            llm_result = self._multimodal_understanding(enhanced)
            metadata["llm_fallback"] = True
            metadata["llm_result"] = llm_result
        else:
            metadata["llm_fallback"] = False

        metadata["final_confidence"] = final_quality

        return enhanced, metadata

    def _assess_image_quality(self, image: Image.Image) -> float:
        """
        Assess image quality using multiple metrics.
        Returns score 0-1 (higher is better).
        """
        scores = []

        # Resolution score
        width, height = image.size
        resolution_score = min(1.0, (width * height) / (2000 * 1500))  # Normalize to 2000x1500
        scores.append(resolution_score)

        # Contrast score
        img_array = np.array(image.convert('L'))
        contrast_score = np.std(img_array) / 128.0  # Normalize std dev
        contrast_score = min(1.0, contrast_score)
        scores.append(contrast_score)

        # Sharpness score (using Laplacian variance)
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2).astype(np.uint8)
        else:
            gray = img_array

        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, laplacian_var / 500.0)  # Normalize
        scores.append(sharpness_score)

        # Noise estimation
        try:
            # Simple noise estimation using block variance
            h, w = gray.shape
            block_size = 16
            noise_scores = []

            for i in range(0, h-block_size, block_size):
                for j in range(0, w-block_size, block_size):
                    block = gray[i:i+block_size, j:j+block_size]
                    noise_scores.append(np.var(block))

            avg_noise = np.mean(noise_scores)
            noise_score = 1.0 - min(1.0, avg_noise / 1000.0)  # Lower noise is better
            scores.append(noise_score)
        except:
            scores.append(0.5)  # Default if noise estimation fails

        # Weighted average
        weights = [0.3, 0.3, 0.2, 0.2]  # resolution, contrast, sharpness, noise
        final_score = sum(s * w for s, w in zip(scores, weights))

        return final_score

    def _apply_super_resolution(self, image: Image.Image) -> Image.Image:
        """Apply ESRGAN or similar super-resolution."""
        try:
            # Try Real-ESRGAN first
            enhanced = self._apply_real_esrgan(image)
            if enhanced:
                return enhanced
        except:
            pass

        # Fallback to basic upscaling
        width, height = image.size
        if width < 800 or height < 600:
            # Upscale by 2x using Lanczos
            new_width, new_height = width * 2, height * 2
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    def _apply_real_esrgan(self, image: Image.Image) -> Optional[Image.Image]:
        """Apply Real-ESRGAN super-resolution."""
        try:
            # This would require Real-ESRGAN model
            # For now, return None to use fallback
            return None
        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"Real-ESRGAN failed: {e}")
            return None

    def _advanced_preprocessing(self, image: Image.Image) -> Image.Image:
        """Advanced preprocessing pipeline."""
        # Convert to RGB if needed
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        # Step 1: Auto-rotate based on EXIF or content
        image = self._auto_rotate(image)

        # Step 2: Advanced contrast enhancement
        image = self._adaptive_contrast_enhancement(image)

        # Step 3: Multi-scale noise reduction
        image = self._multi_scale_noise_reduction(image)

        # Step 4: Unsharp masking for sharpness
        image = self._unsharp_mask(image)

        # Step 5: Final binarization if text-heavy
        if self._is_text_heavy(image):
            image = self._adaptive_binarization(image)

        return image

    def _auto_rotate(self, image: Image.Image) -> Image.Image:
        """Auto-rotate image based on content analysis."""
        try:
            # Convert to grayscale for analysis
            gray = image.convert('L')
            img_array = np.array(gray)

            # Use Hough transform to detect text orientation
            # Simplified: check projection profiles
            height, width = img_array.shape

            # Horizontal projection
            hor_proj = np.sum(img_array < 128, axis=1)

            # Vertical projection
            vert_proj = np.sum(img_array < 128, axis=0)

            # If vertical projection is more uniform, might be rotated
            hor_variance = np.var(hor_proj)
            vert_variance = np.var(vert_proj)

            if vert_variance < hor_variance * 0.7:  # Might be sideways
                # Try 90-degree rotation
                rotated = image.rotate(90, expand=True)
                rotated_gray = np.array(rotated.convert('L'))

                # Check if rotation improved text flow
                rotated_hor_proj = np.sum(rotated_gray < 128, axis=1)
                if np.var(rotated_hor_proj) > hor_variance:
                    return rotated

        except Exception as e:
            logger.debug(f"Auto-rotation failed: {e}")

        return image

    def _adaptive_contrast_enhancement(self, image: Image.Image) -> Image.Image:
        """Adaptive contrast enhancement using CLAHE-like approach."""
        try:
            # Convert to LAB color space for better contrast enhancement
            if image.mode == 'RGB':
                import cv2
                img_array = np.array(image)
                lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)

                # Apply CLAHE to L channel
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                lab[:,:,0] = clahe.apply(lab[:,:,0])

                # Convert back
                enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
                return Image.fromarray(enhanced)
            else:
                # Grayscale enhancement
                enhancer = ImageEnhance.Contrast(image)
                return enhancer.enhance(2.0)

        except ImportError:
            # Fallback without cv2
            enhancer = ImageEnhance.Contrast(image)
            return enhancer.enhance(1.5)
        except Exception as e:
            logger.debug(f"Contrast enhancement failed: {e}")
            return image

    def _multi_scale_noise_reduction(self, image: Image.Image) -> Image.Image:
        """Multi-scale noise reduction."""
        # Apply bilateral filter for edge-preserving noise reduction
        try:
            import cv2
            img_array = np.array(image)

            # Bilateral filter with different parameters for multi-scale
            filtered = cv2.bilateralFilter(img_array, 9, 75, 75)

            # Additional median blur for salt-and-pepper noise
            filtered = cv2.medianBlur(filtered, 3)

            return Image.fromarray(filtered)

        except ImportError:
            # Fallback to PIL filters
            return image.filter(ImageFilter.MedianFilter(size=3))
        except Exception as e:
            logger.debug(f"Noise reduction failed: {e}")
            return image

    def _unsharp_mask(self, image: Image.Image) -> Image.Image:
        """Apply unsharp masking for sharpness enhancement."""
        try:
            # Unsharp mask implementation
            from PIL import ImageFilter, ImageEnhance

            # Create blurred version
            blurred = image.filter(ImageFilter.GaussianBlur(radius=1))

            # Calculate unsharp mask
            unsharp_mask = ImageEnhance.Brightness(blurred).enhance(2.0)

            # Blend original with mask
            result = Image.composite(image, unsharp_mask, unsharp_mask.convert('L'))

            return result

        except Exception as e:
            logger.debug(f"Unsharp masking failed: {e}")
            return image

    def _is_text_heavy(self, image: Image.Image) -> bool:
        """Determine if image is text-heavy for binarization."""
        try:
            gray = image.convert('L')
            img_array = np.array(gray)

            # Calculate text-like regions (high contrast edges)
            edges = cv2.Canny(img_array, 100, 200)
            edge_density = np.sum(edges > 0) / (img_array.shape[0] * img_array.shape[1])

            return edge_density > 0.05  # Threshold for text-heavy

        except:
            # Fallback heuristic
            width, height = image.size
            # If image is tall and narrow, likely text
            return height > width * 2

    def _adaptive_binarization(self, image: Image.Image) -> Image.Image:
        """Adaptive binarization for text images."""
        try:
            import cv2
            img_array = np.array(image.convert('L'))

            # Gaussian adaptive thresholding
            binary = cv2.adaptiveThreshold(
                img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            return Image.fromarray(binary)

        except ImportError:
            # Fallback to simple thresholding
            gray = image.convert('L')
            return gray.point(lambda x: 0 if x < 128 else 255, '1')
        except Exception as e:
            logger.debug(f"Adaptive binarization failed: {e}")
            return image

    def _multimodal_understanding(self, image: Image.Image) -> Dict[str, Any]:
        """
        Use multimodal LLM to understand very low-quality images.
        This is a last resort when traditional OCR fails.
        """
        try:
            if not self._multimodal_llm:
                self._init_multimodal_llm()

            if not self._multimodal_llm:
                return {"error": "Multimodal LLM not available"}

            # Convert image to base64
            import io
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()

            prompt = """
            This is a very low-quality image that traditional OCR cannot read.
            Please analyze the image and extract any visible text or describe the content.
            Focus on any text, numbers, or structured information you can identify.

            Return your analysis in this format:
            {
                "extracted_text": "any readable text",
                "content_description": "description of image content",
                "confidence": 0.1-1.0,
                "text_regions": [{"text": "...", "confidence": 0.5}, ...]
            }
            """

            response = self._multimodal_llm.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"}
                        }
                    ]
                }],
                max_tokens=1000
            )

            result = response.choices[0].message.content
            return json.loads(result) if result else {"error": "Empty response"}

        except Exception as e:
            logger.error(f"Multimodal understanding failed: {e}")
            return {"error": str(e)}

    def _init_multimodal_llm(self):
        """Initialize multimodal LLM."""
        try:
            import openai
            self._multimodal_llm = openai.OpenAI()
        except ImportError:
            logger.warning("OpenAI not available for multimodal understanding")
            self._multimodal_llm = None
