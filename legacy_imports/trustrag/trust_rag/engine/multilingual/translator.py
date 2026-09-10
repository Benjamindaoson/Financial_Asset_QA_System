"""
Translation Engine for GraphRAG.

This module provides translation capabilities for cross-language
information retrieval and multilingual knowledge graph construction.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import hashlib
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class Translator:
    """
    Multilingual translation engine with caching and quality assessment.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize translator.

        Args:
            cache_dir: Directory for caching translations
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path("artifacts/translation_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Translation cache
        self.memory_cache = {}
        self.cache_file = self.cache_dir / "translation_cache.json"

        # Load existing cache
        self._load_cache()

        # Supported language pairs (would be extended based on available models)
        self.supported_pairs = {
            ('en', 'zh'): True,
            ('zh', 'en'): True,
            ('en', 'ja'): True,
            ('ja', 'en'): True,
            ('en', 'ko'): True,
            ('ko', 'en'): True,
            ('en', 'de'): True,
            ('de', 'en'): True,
            ('en', 'fr'): True,
            ('fr', 'en'): True,
            ('zh', 'ja'): False,  # Would need intermediate translation
        }

        # Quality thresholds
        self.quality_thresholds = {
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4
        }

        logger.info("Translator initialized")

    def translate(self, text: str, source_lang: str, target_lang: str,
                 quality: str = 'high') -> Dict[str, Any]:
        """
        Translate text between languages.

        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            quality: Translation quality ('high', 'medium', 'low')

        Returns:
            Translation result with metadata
        """
        if not text or not text.strip():
            return {
                'translated_text': '',
                'confidence': 0.0,
                'method': 'empty_text'
            }

        # Check cache first
        cache_key = self._get_cache_key(text, source_lang, target_lang, quality)
        if cache_key in self.memory_cache:
            cached_result = self.memory_cache[cache_key]
            cached_result['cached'] = True
            return cached_result

        # Check if direct translation is supported
        lang_pair = (source_lang, target_lang)
        if lang_pair not in self.supported_pairs or not self.supported_pairs[lang_pair]:
            # Try intermediate translation through English
            if source_lang != 'en' and target_lang != 'en':
                return self._intermediate_translation(text, source_lang, target_lang, quality)

        # Perform translation
        result = self._perform_translation(text, source_lang, target_lang, quality)

        # Cache result
        self.memory_cache[cache_key] = result
        result['cached'] = False

        # Persist cache periodically
        if len(self.memory_cache) % 100 == 0:
            self._save_cache()

        return result

    def _perform_translation(self, text: str, source_lang: str, target_lang: str,
                           quality: str) -> Dict[str, Any]:
        """
        Perform actual translation (simplified implementation).

        In practice, this would integrate with translation APIs or models
        like Google Translate, DeepL, or open-source models like M2M-100.
        """
        # Simplified mock translation for demonstration
        # In production, this would call actual translation services

        try:
            # Simulate translation delay and quality variation
            import time
            time.sleep(0.01)  # Simulate API call

            # Simple rule-based translation for demo (English-Chinese)
            translated_text = self._mock_translate(text, source_lang, target_lang)

            # Calculate confidence based on text characteristics
            confidence = self._calculate_translation_confidence(text, source_lang, target_lang)

            # Adjust confidence based on quality setting
            quality_multipliers = {'high': 1.0, 'medium': 0.8, 'low': 0.6}
            confidence *= quality_multipliers.get(quality, 0.8)

            return {
                'translated_text': translated_text,
                'original_text': text,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'confidence': min(confidence, 1.0),
                'quality': quality,
                'method': 'mock_translation',  # Would be 'google_translate', 'deepl', etc.
                'character_count': len(text),
                'word_count': len(text.split())
            }

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return {
                'translated_text': text,  # Return original on failure
                'confidence': 0.0,
                'error': str(e)
            }

    def _mock_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Mock translation for demonstration purposes."""
        # Simple English-Chinese translations for demo
        if source_lang == 'en' and target_lang == 'zh':
            translations = {
                'hello': '你好',
                'world': '世界',
                'what is': '什么是',
                'how to': '如何',
                'revenue': '收入',
                'profit': '利润',
                'company': '公司',
                'market': '市场',
                'data': '数据',
                'analysis': '分析'
            }

            translated = text.lower()
            for en, zh in translations.items():
                translated = translated.replace(en, zh)

            return translated

        elif source_lang == 'zh' and target_lang == 'en':
            translations = {
                '你好': 'hello',
                '世界': 'world',
                '什么是': 'what is',
                '如何': 'how to',
                '收入': 'revenue',
                '利润': 'profit',
                '公司': 'company',
                '市场': 'market',
                '数据': 'data',
                '分析': 'analysis'
            }

            translated = text
            for zh, en in translations.items():
                translated = translated.replace(zh, en)

            return translated

        else:
            # For other language pairs, return marked text
            return f"[{target_lang.upper()}] {text}"

    def _calculate_translation_confidence(self, text: str, source_lang: str, target_lang: str) -> float:
        """Calculate translation confidence score."""
        confidence = 0.8  # Base confidence

        # Length factors
        word_count = len(text.split())
        if word_count < 3:
            confidence *= 0.7  # Short texts are harder
        elif word_count > 50:
            confidence *= 0.9  # Long texts generally translate better

        # Language pair factors
        common_pairs = [('en', 'zh'), ('zh', 'en'), ('en', 'ja'), ('ja', 'en')]
        if (source_lang, target_lang) in common_pairs:
            confidence *= 1.1

        # Text complexity factors
        if any(char in text for char in ['®', '™', '©']):  # Special characters
            confidence *= 0.8

        if re.search(r'\d+', text):  # Numbers
            confidence *= 0.9  # Numbers can be tricky

        return min(confidence, 1.0)

    def _intermediate_translation(self, text: str, source_lang: str, target_lang: str,
                                quality: str) -> Dict[str, Any]:
        """Perform translation through intermediate language (English)."""
        try:
            # Translate to English first
            to_english = self.translate(text, source_lang, 'en', quality)

            if to_english['confidence'] < 0.5:
                return {
                    'translated_text': text,
                    'confidence': 0.0,
                    'method': 'intermediate_failed'
                }

            # Then translate to target language
            final_translation = self.translate(
                to_english['translated_text'],
                'en',
                target_lang,
                quality
            )

            # Combine confidence scores
            combined_confidence = to_english['confidence'] * final_translation['confidence']

            return {
                'translated_text': final_translation['translated_text'],
                'original_text': text,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'intermediate_lang': 'en',
                'confidence': combined_confidence,
                'quality': quality,
                'method': 'intermediate_translation'
            }

        except Exception as e:
            logger.error(f"Intermediate translation failed: {e}")
            return {
                'translated_text': text,
                'confidence': 0.0,
                'error': str(e)
            }

    def batch_translate(self, texts: List[str], source_lang: str, target_lang: str,
                       quality: str = 'medium') -> List[Dict[str, Any]]:
        """
        Translate multiple texts efficiently.

        Args:
            texts: List of texts to translate
            source_lang: Source language
            target_lang: Target language
            quality: Translation quality

        Returns:
            List of translation results
        """
        results = []

        for text in texts:
            try:
                result = self.translate(text, source_lang, target_lang, quality)
                results.append(result)
            except Exception as e:
                logger.warning(f"Batch translation failed for text: {e}")
                results.append({
                    'translated_text': text,
                    'confidence': 0.0,
                    'error': str(e)
                })

        return results

    def get_translation_stats(self) -> Dict[str, Any]:
        """Get translation cache and performance statistics."""
        return {
            'cache_size': len(self.memory_cache),
            'cache_file': str(self.cache_file),
            'supported_pairs': list(self.supported_pairs.keys()),
            'quality_thresholds': self.quality_thresholds
        }

    def clear_cache(self):
        """Clear translation cache."""
        self.memory_cache.clear()
        self._save_cache()
        logger.info("Translation cache cleared")

    def _get_cache_key(self, text: str, source_lang: str, target_lang: str, quality: str) -> str:
        """Generate cache key for translation."""
        content = f"{text}|{source_lang}|{target_lang}|{quality}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cache(self):
        """Load translation cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.memory_cache = json.load(f)
                logger.info(f"Loaded {len(self.memory_cache)} cached translations")
        except Exception as e:
            logger.warning(f"Failed to load translation cache: {e}")
            self.memory_cache = {}

    def _save_cache(self):
        """Save translation cache to disk."""
        try:
            # Keep only recent entries to prevent cache from growing too large
            if len(self.memory_cache) > 10000:
                # Keep most recently used items (simplified LRU)
                items = list(self.memory_cache.items())
                self.memory_cache = dict(items[-5000:])

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory_cache, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save translation cache: {e}")

    def detect_and_translate(self, text: str, target_lang: str = 'en',
                           quality: str = 'medium') -> Dict[str, Any]:
        """
        Detect language and translate to target language.

        Args:
            text: Input text
            target_lang: Target language
            quality: Translation quality

        Returns:
            Translation result with language detection
        """
        from .language_detector import LanguageDetector

        detector = LanguageDetector()
        lang_detection = detector.detect_language(text)

        source_lang = lang_detection.get('language', 'unknown')

        if source_lang == target_lang or source_lang == 'unknown':
            return {
                'translated_text': text,
                'detected_lang': source_lang,
                'translation_needed': False,
                'confidence': lang_detection.get('confidence', 0.0)
            }

        # Perform translation
        translation = self.translate(text, source_lang, target_lang, quality)

        return {
            **translation,
            'detected_lang': source_lang,
            'lang_detection_confidence': lang_detection.get('confidence', 0.0),
            'translation_needed': True
        }







