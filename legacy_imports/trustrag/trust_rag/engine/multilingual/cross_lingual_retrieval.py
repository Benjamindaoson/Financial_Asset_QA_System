"""
Cross-Lingual Retrieval for GraphRAG.

This module enables retrieval across multiple languages using
translation and multilingual embeddings.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np

from ..retrieval.strategies.multi_stage_retriever import MultiStageRetriever
from .translator import Translator
from .multilingual_embedder import MultilingualEmbedder

logger = logging.getLogger(__name__)


class CrossLingualRetrieval:
    """
    Cross-lingual retrieval system that enables searching across languages.
    """

    def __init__(
        self,
        base_retriever: MultiStageRetriever,
        translator: Optional[Translator] = None,
        embedder: Optional[MultilingualEmbedder] = None
    ):
        """
        Initialize cross-lingual retrieval.

        Args:
            base_retriever: Base retrieval system
            translator: Translation service
            embedder: Multilingual embedding model
        """
        self.base_retriever = base_retriever
        self.translator = translator or Translator()
        self.embedder = embedder or MultilingualEmbedder()

        # Language preferences and strategies
        self.language_strategies = {
            'translate_query': True,  # Translate query to target languages
            'translate_results': False,  # Translate results back to query language
            'multilingual_index': True,  # Use multilingual embeddings for indexing
            'fallback_to_english': True  # Use English as intermediate language
        }

        # Supported languages for cross-lingual retrieval
        self.supported_languages = [
            'en', 'zh', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru'
        ]

        logger.info("Cross-lingual retrieval initialized")

    def retrieve_cross_lingual(
        self,
        query: str,
        query_lang: str,
        target_langs: Optional[List[str]] = None,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform cross-lingual retrieval.

        Args:
            query: Query string
            query_lang: Query language
            target_langs: Target languages for retrieval
            top_k: Number of results per language
            filters: Optional filters

        Returns:
            Cross-lingual retrieval results
        """
        logger.info(f"Cross-lingual retrieval: {query_lang} -> {target_langs}")

        # Determine target languages
        if target_langs is None:
            target_langs = [lang for lang in self.supported_languages if lang != query_lang]

        results = {
            'original_query': query,
            'query_lang': query_lang,
            'target_langs': target_langs,
            'language_results': {},
            'combined_results': [],
            'translation_info': {}
        }

        # Retrieve in original language
        try:
            original_results = self.base_retriever.retrieve(
                query=query,
                top_k=top_k,
                filters=filters
            )
            results['language_results'][query_lang] = {
                'results': original_results,
                'translated_query': None,
                'method': 'original'
            }
        except Exception as e:
            logger.warning(f"Original language retrieval failed: {e}")
            results['language_results'][query_lang] = {'error': str(e)}

        # Retrieve in target languages
        for target_lang in target_langs:
            try:
                lang_results = self._retrieve_in_language(
                    query, query_lang, target_lang, top_k, filters
                )
                results['language_results'][target_lang] = lang_results
            except Exception as e:
                logger.warning(f"Retrieval in {target_lang} failed: {e}")
                results['language_results'][target_lang] = {'error': str(e)}

        # Combine and rank results
        results['combined_results'] = self._combine_cross_lingual_results(
            results['language_results'], query_lang
        )

        # Add translation metadata
        results['translation_info'] = self._get_translation_info(results['language_results'])

        logger.info(f"Cross-lingual retrieval completed: {len(results['combined_results'])} combined results")

        return results

    def _retrieve_in_language(
        self,
        query: str,
        query_lang: str,
        target_lang: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Retrieve results in a specific target language."""
        # Translate query to target language
        translation = self.translator.translate(query, query_lang, target_lang)

        if translation['confidence'] < 0.6:
            return {
                'results': [],
                'translated_query': translation.get('translated_text'),
                'translation_confidence': translation['confidence'],
                'method': 'translation_low_confidence'
            }

        translated_query = translation['translated_text']

        # Perform retrieval with translated query
        try:
            results = self.base_retriever.retrieve(
                query=translated_query,
                top_k=top_k,
                filters=filters
            )

            return {
                'results': results,
                'translated_query': translated_query,
                'translation_confidence': translation['confidence'],
                'method': 'translated_retrieval'
            }

        except Exception as e:
            logger.warning(f"Translated retrieval failed: {e}")
            return {
                'results': [],
                'translated_query': translated_query,
                'error': str(e),
                'method': 'retrieval_failed'
            }

    def _combine_cross_lingual_results(
        self,
        language_results: Dict[str, Any],
        query_lang: str
    ) -> List[Dict[str, Any]]:
        """Combine and rank results from multiple languages."""
        combined = []

        for lang, lang_data in language_results.items():
            if 'results' not in lang_data or not lang_data['results']:
                continue

            for result in lang_data['results']:
                # Enhance result with language information
                enhanced_result = {
                    'original_result': result,
                    'retrieval_lang': lang,
                    'is_original_lang': lang == query_lang,
                    'translation_confidence': lang_data.get('translation_confidence', 1.0),
                    'translated_query': lang_data.get('translated_query'),
                    'combined_score': self._calculate_combined_score(result, lang_data, query_lang)
                }
                combined.append(enhanced_result)

        # Sort by combined score
        combined.sort(key=lambda x: x['combined_score'], reverse=True)

        # Limit to top results and apply diversity
        final_results = self._apply_diversity_filtering(combined, max_results=50)

        return final_results

    def _calculate_combined_score(
        self,
        result: Any,
        lang_data: Dict[str, Any],
        query_lang: str
    ) -> float:
        """Calculate combined relevance score across languages."""
        base_score = getattr(result, 'score', 0.5)
        translation_confidence = lang_data.get('translation_confidence', 1.0)
        retrieval_lang = lang_data.get('results', [{}])[0].get('lang', 'unknown') if 'results' in lang_data else 'unknown'

        # Language preference bonus
        lang_bonus = 1.0
        if retrieval_lang == query_lang:
            lang_bonus = 1.2  # Prefer original language results
        elif retrieval_lang == 'en':
            lang_bonus = 1.1  # Prefer English as it's often high-quality

        # Translation quality penalty
        translation_penalty = translation_confidence

        # Calculate final score
        combined_score = base_score * lang_bonus * translation_penalty

        return combined_score

    def _apply_diversity_filtering(self, results: List[Dict[str, Any]], max_results: int) -> List[Dict[str, Any]]:
        """Apply diversity filtering to avoid redundant results."""
        if len(results) <= max_results:
            return results

        # Group by semantic similarity (simplified)
        selected = []
        seen_texts = set()

        for result in results:
            # Simple deduplication based on result content
            result_text = str(getattr(result['original_result'], 'text', '')).lower()[:100]

            # Check for similar texts
            is_unique = True
            for seen_text in seen_texts:
                if self._text_similarity(result_text, seen_text) > 0.8:
                    is_unique = False
                    break

            if is_unique:
                selected.append(result)
                seen_texts.add(result_text)

            if len(selected) >= max_results:
                break

        return selected

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 and not words2:
            return 1.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _get_translation_info(self, language_results: Dict[str, Any]) -> Dict[str, Any]:
        """Get translation statistics and info."""
        translation_stats = {
            'total_translations': 0,
            'successful_translations': 0,
            'avg_confidence': 0.0,
            'language_pairs': []
        }

        confidences = []

        for lang, lang_data in language_results.items():
            if 'translated_query' in lang_data and lang_data['translated_query']:
                translation_stats['total_translations'] += 1

                confidence = lang_data.get('translation_confidence', 0)
                if confidence > 0.5:  # Consider successful
                    translation_stats['successful_translations'] += 1
                    confidences.append(confidence)

                # Track language pairs
                query_lang = language_results.get('original_query_lang', 'unknown')
                translation_stats['language_pairs'].append({
                    'from': query_lang,
                    'to': lang,
                    'confidence': confidence
                })

        if confidences:
            translation_stats['avg_confidence'] = np.mean(confidences)

        return translation_stats

    def retrieve_with_fallback(
        self,
        query: str,
        primary_lang: str,
        fallback_langs: List[str] = None,
        top_k: int = 20
    ) -> Dict[str, Any]:
        """
        Retrieve with fallback to other languages if primary fails.

        Args:
            query: Query string
            primary_lang: Primary language
            fallback_langs: Fallback languages
            top_k: Number of results

        Returns:
            Retrieval results with fallback info
        """
        if fallback_langs is None:
            fallback_langs = ['en']  # Default fallback to English

        # Try primary language first
        try:
            primary_results = self.base_retriever.retrieve(query=query, top_k=top_k)
            if primary_results and len(primary_results) >= top_k // 2:
                return {
                    'results': primary_results,
                    'method': 'primary_language',
                    'language': primary_lang,
                    'fallback_used': False
                }
        except Exception as e:
            logger.warning(f"Primary language retrieval failed: {e}")

        # Fallback to other languages
        for fallback_lang in fallback_langs:
            try:
                logger.info(f"Trying fallback to {fallback_lang}")
                fallback_results = self.retrieve_cross_lingual(
                    query, primary_lang, [fallback_lang], top_k
                )

                if fallback_results['language_results'].get(fallback_lang, {}).get('results'):
                    return {
                        'results': fallback_results['language_results'][fallback_lang]['results'],
                        'method': 'fallback_language',
                        'language': fallback_lang,
                        'original_language': primary_lang,
                        'fallback_used': True,
                        'translation_info': fallback_results.get('translation_info')
                    }

            except Exception as e:
                logger.warning(f"Fallback to {fallback_lang} failed: {e}")
                continue

        # Return empty results if all methods fail
        return {
            'results': [],
            'method': 'all_failed',
            'language': None,
            'fallback_used': True,
            'error': 'All retrieval methods failed'
        }

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages for cross-lingual retrieval."""
        return self.supported_languages.copy()

    def update_language_preferences(self, preferences: Dict[str, Any]):
        """Update language processing preferences."""
        self.language_strategies.update(preferences)
        logger.info(f"Updated language preferences: {preferences}")

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get cross-lingual retrieval statistics."""
        return {
            'supported_languages': self.supported_languages,
            'language_strategies': self.language_strategies,
            'translator_stats': self.translator.get_translation_stats() if self.translator else None,
            'embedder_available': self.embedder is not None
        }







