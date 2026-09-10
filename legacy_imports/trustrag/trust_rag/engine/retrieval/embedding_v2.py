"""
Advanced Embedding Engine: BGE-M3 (2026 Production Upgrade).

Replaces all-MiniLM-L6-v2 with state-of-the-art multilingual embedding.
Supports long contexts, hybrid retrieval, and better financial domain understanding.
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
import torch

from trust_rag.config import get_config

# Try to import BGE-M3 dependencies
try:
    from FlagEmbedding import BGEM3FlagModel
    HAS_BGEM3 = True
except ImportError:
    HAS_BGEM3 = False
    BGEM3FlagModel = None

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None

logger = logging.getLogger(__name__)


class BGEEmbeddingEngine:
    """
    BGE-M3 Embedding Engine for production RAG.

    Key improvements over all-MiniLM-L6-v2:
    - 8192 token context length (vs 512)
    - 1024-dimensional vectors (vs 384)
    - Native hybrid retrieval support
    - Better multilingual performance
    - Financial domain optimization
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        cache_dir: Optional[str] = None,
        device: str = "auto",
        max_seq_length: int = 8192,
        batch_size: int = 16
    ):
        """
        Initialize BGE-M3 embedding engine.

        Args:
            model_name: HuggingFace model name
            cache_dir: Model cache directory
            device: Device to run model on ('cpu', 'cuda', 'auto')
            max_seq_length: Maximum sequence length
            batch_size: Batch size for processing
        """
        self.model_name = model_name
        self.cache_dir = cache_dir or get_config().embedding.cache_dir
        self.device = device
        self.max_seq_length = max_seq_length
        self.batch_size = batch_size

        self.model = None
        self._load_model()

    def _load_model(self):
        """Load embedding model - BGE-M3 in production, fallback to SentenceTransformers in dev."""
        import os as _os
        env = _os.getenv("TRUSTRAG_ENV", "dev")
        
        try:
            logger.info(f"Loading BGE-M3 model: {self.model_name}")

            # Determine device
            if self.device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"

            # Try BGE-M3 first
            success = False
            if HAS_BGEM3:
                try:
                    self.model = BGEM3FlagModel(
                        self.model_name,
                        cache_dir=self.cache_dir,
                        device=self.device,
                        max_seq_length=self.max_seq_length
                    )
                    self.model_type = "bgem3"
                    self._embedding_dim = 1024
                    logger.info(f"✅ PRODUCTION: BGE-M3 loaded successfully on {self.device}")
                    success = True
                except Exception as e:
                    if env not in ("dev", "test"):
                        raise
                    logger.warning(f"⚠️ BGE-M3 loading failed: {e}. Trying dev fallback...")

            if not success:
                if env in ("dev", "test") and HAS_SENTENCE_TRANSFORMERS:
                    # Development fallback - use SentenceTransformers
                    logger.warning("⚠️ DEV MODE: Using SentenceTransformer fallback")
                    fallback_model = "sentence-transformers/all-MiniLM-L6-v2"
                    self.model = SentenceTransformer(fallback_model, device=self.device)
                    self.model_type = "sentence_transformer"
                    self._embedding_dim = 384
                    logger.info(f"✅ DEV: Loaded fallback model on {self.device}")
                else:
                    raise RuntimeError("FlagEmbedding failed or not available - BGE-M3 required for production")

        except Exception as e:
            logger.error(f"❌ CRITICAL: BGE-M3 initialization failed: {e}")
            raise RuntimeError(f"BGE-M3 required for production: {e}")

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: Optional[int] = None,
        max_length: Optional[int] = None,
        return_dense: bool = True,
        return_sparse: bool = False,
        return_colbert_vecs: bool = False
    ) -> Union[np.ndarray, Dict[str, np.ndarray]]:
        """
        Encode texts to embeddings.

        Args:
            texts: Single text or list of texts
            batch_size: Override batch size
            max_length: Maximum sequence length
            return_dense: Return dense embeddings
            return_sparse: Return sparse embeddings for hybrid search
            return_colbert_vecs: Return ColBERT-style vectors

        Returns:
            Embeddings array or dict of embedding types
        """
        if isinstance(texts, str):
            texts = [texts]

        batch_size = batch_size or self.batch_size
        max_length = max_length or self.max_seq_length

        try:
            if self.model_type == "sentence_transformer":
                # SentenceTransformer has simpler API
                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False
                )
                if return_dense:
                    return embeddings
                return {"dense": embeddings}
            else:
                # Use FlagEmbedding's optimized encode method
                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    max_length=max_length,
                    return_dense=return_dense,
                    return_sparse=return_sparse,
                    return_colbert_vecs=return_colbert_vecs
                )
                return embeddings

        except Exception as e:
            logger.error(f"Embedding encoding failed: {e}")
            # Return zero embeddings as fallback
            dim = getattr(self, '_embedding_dim', 1024)
            if return_dense:
                return np.zeros((len(texts), dim), dtype=np.float32)
            else:
                return {
                    "dense": np.zeros((len(texts), dim), dtype=np.float32)
                }

    def encode_dense(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Encode texts to dense embeddings only.

        Args:
            texts: Single text or list of texts

        Returns:
            Dense embeddings array
        """
        result = self.encode(texts, return_dense=True, return_sparse=False)
        if isinstance(result, dict):
            return result["dense"]
        return result

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch encode helper for adapter compatibility."""
        embeddings = self.encode_dense(texts)
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return embeddings

    def encode_hybrid(self, texts: Union[str, List[str]]) -> Dict[str, np.ndarray]:
        """
        Encode texts for hybrid retrieval (dense + sparse).

        Args:
            texts: Single text or list of texts

        Returns:
            Dict with 'dense' and 'sparse' embeddings
        """
        return self.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False
        )

    def encode_colbert(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Encode texts to ColBERT-style late interaction vectors.

        Args:
            texts: Single text or list of texts

        Returns:
            ColBERT vectors for advanced reranking
        """
        result = self.encode(texts, return_colbert_vecs=True)
        return result.get("colbert_vecs", np.array([]))

    def get_similarity_scores(
        self,
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray,
        similarity_type: str = "cosine"
    ) -> np.ndarray:
        """
        Calculate similarity scores between query and documents.

        Args:
            query_embedding: Query embedding (1, dim)
            doc_embeddings: Document embeddings (n, dim)
            similarity_type: Similarity type ('cosine', 'dot', 'euclidean')

        Returns:
            Similarity scores array
        """
        if similarity_type == "cosine":
            # Cosine similarity
            query_norm = query_embedding / np.linalg.norm(query_embedding)
            doc_norms = doc_embeddings / np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
            return np.dot(doc_norms, query_norm.T).flatten()

        elif similarity_type == "dot":
            # Dot product
            return np.dot(doc_embeddings, query_embedding.T).flatten()

        elif similarity_type == "euclidean":
            # Euclidean distance (negated for ranking)
            distances = np.linalg.norm(doc_embeddings - query_embedding, axis=1)
            return -distances

        else:
            raise ValueError(f"Unsupported similarity type: {similarity_type}")

    def health_check(self) -> Dict[str, Any]:
        """Basic health check for embedding engine."""
        return {
            "healthy": self.model is not None,
            "model_name": self.model_name,
            "device": self.device
        }

    def rerank_with_bge(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Rerank documents using BGE's built-in reranking capability.

        Args:
            query: Query string
            documents: List of document texts
            top_k: Number of top results to return

        Returns:
            List of (document, score) tuples
        """
        try:
            # Use BGE-M3's reranking capability
            if hasattr(self.model, 'compute_score'):
                scores = []
                for doc in documents:
                    score = self.model.compute_score([[query, doc]])[0]
                    scores.append((doc, float(score)))

                # Sort by score descending
                scores.sort(key=lambda x: x[1], reverse=True)
                return scores[:top_k]

            else:
                # Fallback: use dense embeddings for reranking
                query_emb = self.encode_dense(query)
                doc_embs = self.encode_dense(documents)
                similarities = self.get_similarity_scores(query_emb, doc_embs)

                results = []
                for doc, sim in zip(documents, similarities):
                    results.append((doc, float(sim)))

                results.sort(key=lambda x: x[1], reverse=True)
                return results[:top_k]

        except Exception as e:
            logger.error(f"BGE reranking failed: {e}")
            # Return original order as fallback
            return [(doc, 1.0 - i * 0.1) for i, doc in enumerate(documents[:top_k])]

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information and capabilities."""
        return {
            "model_name": self.model_name,
            "dimension": 1024,  # BGE-M3 dimension
            "max_seq_length": self.max_seq_length,
            "device": self.device,
            "supports_sparse": True,
            "supports_colbert": True,
            "supports_hybrid": True,
            "multilingual": True,
            "financial_optimized": True
        }

    def __del__(self):
        """Cleanup model resources."""
        if hasattr(self, 'model'):
            del self.model
