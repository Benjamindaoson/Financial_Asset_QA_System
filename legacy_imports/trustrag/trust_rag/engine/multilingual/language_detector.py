"""
Language Detection for GraphRAG.

This module provides accurate language detection and script identification
for multilingual text processing.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import re
from collections import Counter
import langdetect
from langdetect.lang_detect_exception import LangDetectError

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Advanced language detection with confidence scoring and script analysis.
    """

    def __init__(self):
        """Initialize language detector."""
        # Language code mappings
        self.language_names = {
            'en': 'English',
            'zh': 'Chinese',
            'zh-cn': 'Chinese (Simplified)',
            'zh-tw': 'Chinese (Traditional)',
            'ja': 'Japanese',
            'ko': 'Korean',
            'de': 'German',
            'fr': 'French',
            'es': 'Spanish',
            'pt': 'Portuguese',
            'it': 'Italian',
            'ru': 'Russian',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'th': 'Thai',
            'vi': 'Vietnamese',
            'id': 'Indonesian',
            'ms': 'Malay'
        }

        # Script patterns for fallback detection
        self.script_patterns = {
            'zh': re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]'),
            'ja': re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]'),
            'ko': re.compile(r'[\uac00-\ud7af\u1100-\u11ff]'),
            'ar': re.compile(r'[\u0600-\u06ff\u0750-\u077f]'),
            'hi': re.compile(r'[\u0900-\u097f]'),
            'ru': re.compile(r'[\u0400-\u04ff]'),
            'th': re.compile(r'[\u0e00-\u0e7f]')
        }

        # Language-specific keywords for validation
        self.language_keywords = {
            'zh': ['的', '是', '在', '有', '这', '那', '你', '我', '他'],
            'ja': ['です', 'ます', 'ました', 'さん', 'ちゃん', 'くん'],
            'ko': ['이다', '하다', '있다', '없다', '되다', '이다'],
            'de': ['der', 'die', 'das', 'und', 'ist', 'in', 'auf'],
            'fr': ['le', 'la', 'les', 'et', 'est', 'dans', 'sur'],
            'es': ['el', 'la', 'los', 'las', 'y', 'es', 'en'],
            'pt': ['o', 'a', 'os', 'as', 'e', 'é', 'em'],
            'it': ['il', 'la', 'i', 'le', 'e', 'è', 'in']
        }

        logger.info("Language detector initialized")

    def detect_language(self, text: str, confidence_threshold: float = 0.6) -> Dict[str, Any]:
        """
        Detect language of input text.

        Args:
            text: Input text
            confidence_threshold: Minimum confidence threshold

        Returns:
            Language detection results
        """
        if not text or not text.strip():
            return {
                'language': 'unknown',
                'confidence': 0.0,
                'method': 'empty_text'
            }

        # Clean text
        clean_text = self._clean_text(text)

        if len(clean_text) < 3:
            return {
                'language': 'unknown',
                'confidence': 0.0,
                'method': 'insufficient_text'
            }

        # Try primary detection
        primary_result = self._primary_detection(clean_text)

        if primary_result['confidence'] >= confidence_threshold:
            return primary_result

        # Try fallback methods
        fallback_result = self._fallback_detection(clean_text)

        # Return best result
        if fallback_result['confidence'] > primary_result['confidence']:
            return fallback_result
        else:
            return primary_result

    def _primary_detection(self, text: str) -> Dict[str, Any]:
        """Primary language detection using langdetect."""
        try:
            # Use langdetect for primary detection
            detected_langs = langdetect.detect_langs(text)

            if detected_langs:
                best_lang = detected_langs[0]
                confidence = best_lang.prob

                # Validate with script patterns
                script_confidence = self._validate_with_script(text, best_lang.lang)
                final_confidence = min(confidence * 1.2, script_confidence * 0.8 + confidence * 0.2, 1.0)

                return {
                    'language': best_lang.lang,
                    'language_name': self.language_names.get(best_lang.lang, best_lang.lang),
                    'confidence': final_confidence,
                    'method': 'langdetect',
                    'all_candidates': [{'lang': l.lang, 'prob': l.prob} for l in detected_langs]
                }

        except LangDetectError:
            pass
        except Exception as e:
            logger.warning(f"Primary detection failed: {e}")

        return {
            'language': 'unknown',
            'confidence': 0.0,
            'method': 'primary_failed'
        }

    def _fallback_detection(self, text: str) -> Dict[str, Any]:
        """Fallback language detection using script analysis."""
        # Script-based detection
        script_scores = {}

        for lang_code, pattern in self.script_patterns.items():
            matches = len(pattern.findall(text))
            if matches > 0:
                # Score based on character matches and text length
                score = min(matches / len(text) * 10, 1.0)
                script_scores[lang_code] = score

        # Keyword-based detection
        keyword_scores = {}
        words = re.findall(r'\b\w+\b', text.lower())

        for lang_code, keywords in self.language_keywords.items():
            matches = sum(1 for word in words if word in keywords)
            if matches > 0:
                score = min(matches / len(words) * 5, 1.0)
                keyword_scores[lang_code] = score

        # Combine scores
        combined_scores = {}
        for lang_code in set(script_scores.keys()) | set(keyword_scores.keys()):
            script_score = script_scores.get(lang_code, 0)
            keyword_score = keyword_scores.get(lang_code, 0)
            combined_scores[lang_code] = (script_score + keyword_score) / 2

        if combined_scores:
            best_lang = max(combined_scores, key=combined_scores.get)
            confidence = combined_scores[best_lang]

            return {
                'language': best_lang,
                'language_name': self.language_names.get(best_lang, best_lang),
                'confidence': confidence,
                'method': 'fallback_script_keywords',
                'script_score': script_scores.get(best_lang, 0),
                'keyword_score': keyword_scores.get(best_lang, 0)
            }

        return {
            'language': 'unknown',
            'confidence': 0.0,
            'method': 'fallback_failed'
        }

    def detect_languages_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Detect languages for multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of language detection results
        """
        results = []

        for text in texts:
            try:
                result = self.detect_language(text)
                results.append(result)
            except Exception as e:
                logger.warning(f"Batch detection failed for text: {e}")
                results.append({
                    'language': 'unknown',
                    'confidence': 0.0,
                    'method': 'error'
                })

        return results

    def get_language_stats(self, texts: List[str]) -> Dict[str, Any]:
        """
        Get language distribution statistics.

        Args:
            texts: List of texts

        Returns:
            Language statistics
        """
        detections = self.detect_languages_batch(texts)

        # Count languages
        lang_counts = Counter()
        confidence_sum = 0
        valid_detections = 0

        for detection in detections:
            lang = detection.get('language', 'unknown')
            confidence = detection.get('confidence', 0)

            lang_counts[lang] += 1

            if confidence > 0:
                confidence_sum += confidence
                valid_detections += 1

        # Calculate statistics
        total_texts = len(texts)
        unique_languages = len(lang_counts)

        stats = {
            'total_texts': total_texts,
            'unique_languages': unique_languages,
            'language_distribution': dict(lang_counts),
            'avg_confidence': confidence_sum / max(valid_detections, 1),
            'detection_rate': valid_detections / total_texts,
            'dominant_language': lang_counts.most_common(1)[0][0] if lang_counts else 'unknown'
        }

        return stats

    def _clean_text(self, text: str) -> str:
        """Clean text for language detection."""
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Remove excessive punctuation
        text = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u1100-\u11ff\u0600-\u06ff\u0750-\u077f\u0900-\u097f\u0e00-\u0e7f]+', ' ', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        return text.strip()

    def _validate_with_script(self, text: str, detected_lang: str) -> float:
        """Validate detected language with script patterns."""
        if detected_lang in self.script_patterns:
            pattern = self.script_patterns[detected_lang]
            matches = pattern.findall(text)

            if matches:
                # Calculate script confidence
                script_ratio = len(matches) / len(text) if text else 0

                # Adjust based on language expectations
                if detected_lang in ['zh', 'ja', 'ko']:
                    # Asian languages should have high script ratio
                    return min(script_ratio * 3, 1.0)
                else:
                    # Other languages may have mixed scripts
                    return min(script_ratio * 2 + 0.3, 1.0)

        return 0.5  # Neutral confidence if no script validation

    def is_mixed_language(self, text: str, threshold: float = 0.1) -> Dict[str, Any]:
        """
        Check if text contains multiple languages.

        Args:
            text: Input text
            threshold: Minimum proportion for secondary language

        Returns:
            Mixed language analysis
        """
        # Split text into segments (approximate sentences)
        segments = re.split(r'[.!?。！？\n]+', text)
        segments = [s.strip() for s in segments if s.strip() and len(s.strip()) > 10]

        if len(segments) < 2:
            return {
                'is_mixed': False,
                'languages': [],
                'confidence': 0.0
            }

        # Detect language for each segment
        segment_languages = []
        for segment in segments[:10]:  # Limit analysis
            detection = self.detect_language(segment)
            if detection['confidence'] > 0.5:
                segment_languages.append(detection['language'])

        # Count language distribution
        lang_counts = Counter(segment_languages)
        total_segments = len(segment_languages)

        if total_segments < 2:
            return {
                'is_mixed': False,
                'languages': list(lang_counts.keys()),
                'confidence': 0.0
            }

        # Check for mixed languages
        dominant_lang, dominant_count = lang_counts.most_common(1)[0]
        dominant_ratio = dominant_count / total_segments

        is_mixed = dominant_ratio < (1 - threshold)
        mixed_languages = [lang for lang, count in lang_counts.items()
                          if count / total_segments >= threshold]

        return {
            'is_mixed': is_mixed,
            'languages': mixed_languages,
            'dominant_language': dominant_lang,
            'confidence': 1 - dominant_ratio if is_mixed else 0.0
        }

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get list of supported languages.

        Returns:
            List of supported languages with codes and names
        """
        return [
            {'code': code, 'name': name}
            for code, name in self.language_names.items()
        ]

    def get_language_info(self, lang_code: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a language.

        Args:
            lang_code: Language code

        Returns:
            Language information or None
        """
        if lang_code in self.language_names:
            return {
                'code': lang_code,
                'name': self.language_names[lang_code],
                'has_script_pattern': lang_code in self.script_patterns,
                'has_keywords': lang_code in self.language_keywords
            }

        return None







