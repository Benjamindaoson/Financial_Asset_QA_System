"""
Multilingual Embedder for GraphRAG.

This module provides multilingual embedding capabilities using
models like mBERT, XLM-R, and LaBSE for cross-language similarity.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)


class MultilingualEmbedder:
    """
    Multilingual embedding model for cross-language text similarity.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/LaBSE",
        device: str = "auto",
        max_length: int = 512
    ):
        """
        Initialize multilingual embedder.

        Args:
            model_name: Multilingual embedding model name
            device: Device to run model on
            max_length: Maximum sequence length
        """
        self.model_name = model_name
        self.max_length = max_length
        self.device = self._setup_device(device)

        # Initialize model and tokenizer
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            logger.info(f"Multilingual embedder loaded: {model_name}")
        except Exception as e:
            logger.warning(f"Failed to load multilingual model {model_name}: {e}")
            # Fallback to simple embedder
            self.model = None
            self.tokenizer = None

        # Supported languages (would be model-dependent)
        self.supported_languages = [
            'en', 'zh', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru',
            'ar', 'hi', 'th', 'vi', 'id', 'ms', 'nl', 'pl', 'tr', 'cs'
        ]

        # Embedding cache
        self.embedding_cache = {}
        self.cache_max_size = 10000

        logger.info("Multilingual embedder initialized")

    def _setup_device(self, device: str) -> str:
        """Setup compute device."""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def encode(self, texts: Union[str, List[str]], lang: Optional[str] = None) -> np.ndarray:
        """
        Encode text(s) to multilingual embeddings.

        Args:
            texts: Text or list of texts
            lang: Language hint (optional)

        Returns:
            Embedding array
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.array([])

        # Check cache first
        cache_key = self._get_cache_key(texts, lang)
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]

        # Generate embeddings
        embeddings = self._generate_embeddings(texts, lang)

        # Cache results
        if len(self.embedding_cache) < self.cache_max_size:
            self.embedding_cache[cache_key] = embeddings

        return embeddings

    def _generate_embeddings(self, texts: List[str], lang: Optional[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        if not self.model or not self.tokenizer:
            # Fallback: return random embeddings
            logger.warning("Using fallback random embeddings")
            return np.random.randn(len(texts), 768).astype(np.float32)

        try:
            # Prepare inputs
            inputs = self.tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                embeddings = self._mean_pooling(outputs.last_hidden_state, inputs['attention_mask'])

                # Normalize embeddings
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

            return embeddings.cpu().numpy()

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Return zero embeddings as fallback
            return np.zeros((len(texts), 768), dtype=np.float32)

    def _mean_pooling(self, token_embeddings: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Perform mean pooling on token embeddings."""
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask

    def similarity(self, text1: str, text2: str, lang1: Optional[str] = None, lang2: Optional[str] = None) -> float:
        """
        Calculate similarity between two texts (potentially in different languages).

        Args:
            text1: First text
            text2: Second text
            lang1: Language of first text
            lang2: Language of second text

        Returns:
            Similarity score (0-1)
        """
        try:
            # Encode both texts
            emb1 = self.encode(text1, lang1)
            emb2 = self.encode(text2, lang2)

            if len(emb1) == 0 or len(emb2) == 0:
                return 0.0

            # Calculate cosine similarity
            similarity = np.dot(emb1[0], emb2[0]) / (
                np.linalg.norm(emb1[0]) * np.linalg.norm(emb2[0])
            )

            # Ensure similarity is between 0 and 1
            return max(0.0, min(1.0, (similarity + 1) / 2))

        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0

    def batch_similarity(self, query: str, candidates: List[str],
                        query_lang: Optional[str] = None,
                        candidate_langs: Optional[List[str]] = None) -> List[float]:
        """
        Calculate similarities between query and multiple candidates.

        Args:
            query: Query text
            candidates: List of candidate texts
            query_lang: Query language
            candidate_langs: Candidate languages (optional)

        Returns:
            List of similarity scores
        """
        try:
            # Encode query
            query_emb = self.encode(query, query_lang)

            # Encode candidates
            candidate_embs = self.encode(candidates, candidate_langs[0] if candidate_langs else None)

            if len(query_emb) == 0 or len(candidate_embs) == 0:
                return [0.0] * len(candidates)

            # Calculate similarities
            similarities = []
            for cand_emb in candidate_embs:
                sim = np.dot(query_emb[0], cand_emb) / (
                    np.linalg.norm(query_emb[0]) * np.linalg.norm(cand_emb)
                )
                # Normalize to 0-1 range
                sim = max(0.0, min(1.0, (sim + 1) / 2))
                similarities.append(sim)

            return similarities

        except Exception as e:
            logger.error(f"Batch similarity calculation failed: {e}")
            return [0.0] * len(candidates)

    def find_similar_across_languages(
        self,
        query: str,
        candidate_texts: Dict[str, List[str]],
        query_lang: str,
        top_k: int = 10
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Find similar texts across multiple languages.

        Args:
            query: Query text
            candidate_texts: Dictionary of language -> list of texts
            query_lang: Query language
            top_k: Number of top results per language

        Returns:
            Dictionary of language -> list of (text, score) tuples
        """
        results = {}

        for lang, texts in candidate_texts.items():
            if not texts:
                continue

            try:
                # Calculate similarities
                similarities = self.batch_similarity(query, texts, query_lang, [lang] * len(texts))

                # Get top-k results
                text_score_pairs = list(zip(texts, similarities))
                text_score_pairs.sort(key=lambda x: x[1], reverse=True)

                results[lang] = text_score_pairs[:top_k]

            except Exception as e:
                logger.warning(f"Similarity calculation failed for {lang}: {e}")
                results[lang] = []

        return results

    def cluster_multilingual_texts(
        self,
        texts: List[str],
        languages: List[str],
        n_clusters: int = 5
    ) -> Dict[str, Any]:
        """
        Cluster texts from multiple languages based on semantic similarity.

        Args:
            texts: List of texts
            languages: Corresponding languages
            n_clusters: Number of clusters

        Returns:
            Clustering results
        """
        try:
            # Generate embeddings
            embeddings = self.encode(texts)

            if len(embeddings) == 0:
                return {'error': 'Failed to generate embeddings'}

            # Perform clustering (simplified - would use sklearn in practice)
            from sklearn.cluster import KMeans

            kmeans = KMeans(n_clusters=min(n_clusters, len(texts)), random_state=42)
            cluster_labels = kmeans.fit_predict(embeddings)

            # Organize results
            clusters = {}
            for i, (text, lang, label) in enumerate(zip(texts, languages, cluster_labels)):
                if label not in clusters:
                    clusters[label] = {
                        'texts': [],
                        'languages': [],
                        'centroid': kmeans.cluster_centers_[label]
                    }

                clusters[label]['texts'].append(text)
                clusters[label]['languages'].append(lang)

            return {
                'clusters': clusters,
                'n_clusters': len(clusters),
                'cluster_sizes': [len(cluster['texts']) for cluster in clusters.values()],
                'language_distribution': self._analyze_cluster_languages(clusters)
            }

        except Exception as e:
            logger.error(f"Multilingual clustering failed: {e}")
            return {'error': str(e)}

    def _analyze_cluster_languages(self, clusters: Dict) -> Dict[str, Any]:
        """Analyze language distribution in clusters."""
        lang_dist = {}

        for cluster_id, cluster_data in clusters.items():
            lang_counts = {}
            for lang in cluster_data['languages']:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            lang_dist[cluster_id] = lang_counts

        return lang_dist

    def translate_and_embed(
        self,
        text: str,
        source_lang: str,
        target_lang: str = 'en'
    ) -> Dict[str, Any]:
        """
        Translate text and generate embeddings for both original and translated versions.

        Args:
            text: Input text
            source_lang: Source language
            target_lang: Target language for translation

        Returns:
            Dictionary with original and translated embeddings
        """
        from .translator import Translator

        translator = Translator()

        # Translate text
        translation = translator.translate(text, source_lang, target_lang)

        # Generate embeddings
        original_emb = self.encode(text, source_lang)
        translated_emb = self.encode(translation.get('translated_text', ''), target_lang)

        return {
            'original_text': text,
            'translated_text': translation.get('translated_text', ''),
            'original_embedding': original_emb,
            'translated_embedding': translated_emb,
            'translation_confidence': translation.get('confidence', 0.0),
            'cross_lingual_similarity': self._calculate_embedding_similarity(
                original_emb, translated_emb
            ) if len(original_emb) > 0 and len(translated_emb) > 0 else 0.0
        }

    def _calculate_embedding_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings."""
        if len(emb1) == 0 or len(emb2) == 0:
            return 0.0

        similarity = np.dot(emb1[0], emb2[0]) / (
            np.linalg.norm(emb1[0]) * np.linalg.norm(emb2[0])
        )

        return max(0.0, min(1.0, (similarity + 1) / 2))

    def _get_cache_key(self, texts: List[str], lang: Optional[str]) -> str:
        """Generate cache key for embeddings."""
        import hashlib

        # Create a deterministic key
        content = '|'.join(texts) + f"|{lang or 'unknown'}"
        return hashlib.md5(content.encode()).hexdigest()

    def clear_cache(self):
        """Clear embedding cache."""
        self.embedding_cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_size': len(self.embedding_cache),
            'max_cache_size': self.cache_max_size,
            'cache_utilization': len(self.embedding_cache) / self.cache_max_size
        }

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return self.supported_languages.copy()

    def is_language_supported(self, lang: str) -> bool:
        """Check if language is supported."""
        return lang in self.supported_languages

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'max_length': self.max_length,
            'supported_languages': len(self.supported_languages),
            'model_loaded': self.model is not None,
            'tokenizer_loaded': self.tokenizer is not None,
            'cache_stats': self.get_cache_stats()
        }







