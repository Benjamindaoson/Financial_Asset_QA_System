"""
Real Embedding Implementation for TrustRAG.
Supports local sentence-transformers and remote OpenAI/Qwen models.
"""
import logging
import hashlib
import os
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
import numpy as np

from trust_rag.config import get_config

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Embed a single query."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class SentenceTransformersProvider(EmbeddingProvider):
    """Local sentence-transformers provider."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_dir: Optional[str] = None):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        self._dimension = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=self.cache_dir,
                    device='cpu'  # Use CPU for now
                )
                # Get dimension from a sample embedding
                sample = self._model.encode(["test"])
                self._dimension = len(sample[0])
                logger.info(f"Loaded sentence-transformers model: {self.model_name}, dimension: {self._dimension}")
            except ImportError:
                logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Failed to load sentence-transformers model: {e}")
                raise

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        self._load_model()
        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to embed texts: {e}")
            raise

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query."""
        self._load_model()
        try:
            embedding = self._model.encode([query], convert_to_numpy=True)[0]
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        if self._dimension is None:
            self._load_model()
        return self._dimension

    def is_available(self) -> bool:
        """Check if sentence-transformers is available."""
        try:
            import sentence_transformers
            return True
        except ImportError:
            return False


class OpenAIProvider(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "text-embedding-ada-002"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.model = model
        self._dimension = 1536  # text-embedding-ada-002 dimension
        self._client = None

    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                logger.error("openai not installed. Install with: pip install openai")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts using OpenAI."""
        self._get_client()
        try:
            response = self._client.embeddings.create(
                input=texts,
                model=self.model
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"Failed to get embeddings from OpenAI: {e}")
            raise

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query using OpenAI."""
        return self.embed_texts([query])[0]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        if not self.api_key:
            return False
        try:
            import openai
            return True
        except ImportError:
            return False


class EmbeddingManager:
    """
    Unified embedding manager supporting multiple providers.
    """

    def __init__(self, config=None):
        self.config = config or get_config().embedding
        self._provider: Optional[EmbeddingProvider] = None
        # Use centralized CacheManager for TTL support
        self.cache_manager = CacheManager()


    def _get_provider(self) -> EmbeddingProvider:
        """Lazy load the appropriate provider."""
        if self._provider is None:
            provider_name = self.config.provider.lower()

            if provider_name == "sentence-transformers":
                self._provider = SentenceTransformersProvider(
                    model_name=self.config.model_name,
                    cache_dir=self.config.cache_dir
                )
            elif provider_name in ["openai", "qwen"]:
                self._provider = OpenAIProvider(
                    api_key=os.getenv(self.config.api_key_env),
                    base_url=self.config.base_url,
                    model=self.config.model_name
                )
            else:
                raise ValueError(f"Unsupported embedding provider: {provider_name}")

            if not self._provider.is_available():
                raise RuntimeError(f"Embedding provider {provider_name} is not available")

        return self._provider

    def embed_texts(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """Embed multiple texts with optional caching."""
        if not texts:
            return []

        provider = self._get_provider()
        result = []

        # Check cache first
        uncached_texts = []
        uncached_indices = []

        if use_cache and self.config.enable_cache:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                # Use CacheManager
                cached_embedding = self.cache_manager.get(cache_key)
                if cached_embedding is not None:
                    result.append(cached_embedding)
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
                    result.append(None)  # Placeholder
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))

        # Embed uncached texts
        if uncached_texts:
            try:
                embeddings = provider.embed_texts(uncached_texts)

                # Update cache and result
                for i, (idx, embedding) in enumerate(zip(uncached_indices, embeddings)):
                    if use_cache and self.config.enable_cache:
                        cache_key = self._get_cache_key(uncached_texts[i])
                        # Cache with default embedding TTL (e.g. 2 hours)
                        self.cache_manager.put(
                            cache_key, 
                            embedding, 
                            ttl=self.cache_manager.ttl_configs.get('embeddings', 7200)
                        )
                    result[idx] = embedding

            except Exception as e:
                logger.error(f"Failed to embed texts: {e}")
                # Return zero vectors as fallback
                zero_vector = [0.0] * provider.dimension
                for idx in uncached_indices:
                    result[idx] = zero_vector

        return result

    def embed_query(self, query: str, use_cache: bool = True) -> List[float]:
        """Embed a single query with optional caching."""
        if use_cache and self.config.enable_cache:
            cache_key = self._get_cache_key(query)
            cached_embedding = self.cache_manager.get(cache_key)
            if cached_embedding is not None:
                return cached_embedding

        provider = self._get_provider()
        embedding = provider.embed_query(query)

        if use_cache and self.config.enable_cache:
            cache_key = self._get_cache_key(query)
            self.cache_manager.put(
                cache_key, 
                embedding, 
                ttl=self.cache_manager.ttl_configs.get('embeddings', 7200)
            )

        return embedding

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Prefix with 'emb_' to avoid collisions
        return f"emb_{hashlib.md5(text.encode('utf-8')).hexdigest()}"

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._get_provider().dimension

    def is_available(self) -> bool:
        """Check if embedding service is available."""
        try:
            provider = self._get_provider()
            return provider.is_available()
        except Exception:
            return False

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()

    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
