"""
RetrievalAdapter - Vector Retrieval Adapter

Full implementation of BGE-M3 + pgvector hybrid retrieval pipeline:
1. BGE-M3 vector encoding (1024d, 8192 tokens)
2. PostgreSQL + pgvector storage (ACID compliant)
3. Dense + Sparse + Metadata hybrid retrieval
4. Real-time index updates and incremental synchronization

This is the core component for TrustRAG 2.0 production deployment.
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from trust_rag.config import get_config
from trust_rag.engine.retrieval.embedding_v2 import BGEEmbeddingEngine
from trust_rag.engine.retrieval.vector_store import PostgreSQLVectorStore, VectorChunk
from trust_rag.engine.retrieval.bm25_store import BM25Store
from trust_rag.engine.retrieval.scorer import HybridScorer
from trust_rag.engine.retrieval.reranker_v2 import BGEReranker
from trust_rag.core.exceptions import RetrievalFailedException

logger = logging.getLogger(__name__)


class QueryCache:
    """LRU Cache with TTL to prevent memory leaks."""
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        from collections import OrderedDict
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache = OrderedDict()
        
    def __getitem__(self, key):
        if key not in self._cache:
            raise KeyError(key)
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            raise KeyError(key)
            
        # Move to end (LRU)
        self._cache.move_to_end(key)
        return value
        
    def __setitem__(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())
        
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)
            
    def __contains__(self, key):
        if key not in self._cache:
            return False
            
        _, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return False
            
        return True
        
    def clear(self):
        self._cache.clear()
        
    def __len__(self):
        return len(self._cache)

@dataclass
class RetrievalRequest:
    query: str
    tier: str
    strategy: "RetrievalStrategy"
    top_k: int
    filters: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None
    boost_anchors: Optional[List[str]] = None


class RetrievalStrategy(str):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    MULTIVECTOR = "multivector"


@dataclass
class RawCandidate:
    chunk_id: str
    evidence_id: str
    doc_id: str
    text: str
    tier: str
    strategy: str
    dense_score: float = 0.0
    sparse_score: float = 0.0
    anchor_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RetrievalResult:
    """Retrieval result artifact."""
    chunk: VectorChunk
    score: float
    rank: int
    retrieval_type: str  # 'dense', 'sparse', 'hybrid'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridRetrievalConfig:
    """Hybrid retrieval configuration."""
    # Dense retrieval configuration
    dense_weight: float = 0.4
    dense_top_k: int = 50

    # Sparse retrieval configuration
    sparse_weight: float = 0.4
    sparse_top_k: int = 50

    # Metadata filtering configuration
    enable_metadata_filter: bool = True
    metadata_boost_factor: float = 1.2

    # Fusion configuration
    fusion_method: str = "weighted_sum"  # weighted_sum, rrf, custom
    final_top_k: int = 20

    # Performance configuration
    batch_size: int = 16
    timeout_ms: int = 3000


class RetrievalAdapter:
    """
    Vector Retrieval Adapter - TrustRAG 2.0 Core Component

    Implements the full retrieval pipeline:
    1. BGE-M3 encoding + BM25 + Metadata
    2. PostgreSQL + pgvector storage
    3. Hybrid retrieval fusion algorithm
    4. Real-time index management and incremental updates
    """

    def __init__(
        self,
        embedding_engine: Optional[BGEEmbeddingEngine] = None,
        vector_store: Optional[Any] = None,
        bm25_store: Optional[BM25Store] = None,
        reranker: Optional[BGEReranker] = None,
        config: Optional[HybridRetrievalConfig] = None
    ):
        """
        Initializes the Retrieval Adapter - production requires all components to be available.
        """
        self.config = config or HybridRetrievalConfig()

        # Force initialize BGE-M3 engine
        try:
            self.embedding_engine = embedding_engine or BGEEmbeddingEngine()
            logger.info("✅ BGE-M3 embedding engine initialized")
        except Exception as e:
            logger.error(f"❌ CRITICAL: Cannot initialize BGE-M3 engine: {e}")
            raise RuntimeError(f"BGE-M3 engine required for production: {e}")

        # Initialize pgvector store (dev mode allows fallback)
        import os as _os
        env = _os.getenv("TRUSTRAG_ENV", "dev")
        try:
            self.vector_store = vector_store or PostgreSQLVectorStore()
            logger.info("✅ PostgreSQL + pgvector store initialized")
            self._using_mock_store = False
        except Exception as e:
            if env in ("dev", "test"):
                logger.warning(f"⚠️ DEV MODE: PostgreSQL unavailable, using mock store: {e}")
                self.vector_store = self._create_mock_vector_store()
                self._using_mock_store = True
            else:
                logger.error(f"❌ CRITICAL: Cannot initialize pgvector store: {e}")
                raise RuntimeError(f"pgvector store required for production: {e}")

        # Initialize BM25 store
        try:
            self.bm25_store = bm25_store or BM25Store()
            logger.info("✅ BM25 store initialized")
        except Exception as e:
            logger.error(f"❌ CRITICAL: Cannot initialize BM25 store: {e}")
            raise RuntimeError(f"BM25 store required for production: {e}")

        # P0: BGE-Reranker is MANDATORY - no fallback allowed
        try:
            self.reranker = reranker or BGEReranker()
            logger.info("✅ BGE-Reranker initialized (MANDATORY)")
        except Exception as e:
            logger.error(f"❌ CRITICAL: BGE-Reranker REQUIRED for production: {e}")
            raise RuntimeError(f"BGE-Reranker required for production: {e}")

        self.scorer = HybridScorer()

        # Cache and performance monitoring
        self._query_cache = QueryCache(max_size=1000, ttl_seconds=300)
        self._performance_stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "avg_dense_time": 0.0,
            "avg_sparse_time": 0.0,
            "avg_fusion_time": 0.0,
            "avg_rerank_time": 0.0
        }


        # Attempt to auto-load BM25 index
        bm25_path = get_config().paths.bm25_index_file
        if os.path.exists(bm25_path):
            try:
                self.bm25_store.load(bm25_path)
                logger.info(f"✅ Auto-loaded BM25 index from {bm25_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to auto-load BM25 index: {e}")

        logger.info("✅ PRODUCTION: RetrievalAdapter fully initialized with BGE-M3 + pgvector + BM25 + Reranker")

    def _create_mock_vector_store(self):
        """Create an in-memory mock vector store for dev/test when PostgreSQL unavailable."""
        class MockVectorStore:
            def __init__(self):
                self._chunks = {}
                logger.info("🔧 MockVectorStore created for dev mode")
            
            def add_chunks(self, chunks):
                for chunk in chunks:
                    self._chunks[chunk.chunk_id] = chunk
                return len(chunks)
            
            def search(self, query_embedding, top_k=20, filters=None, query_text=None, use_hybrid=False):
                # Simple cosine similarity search
                import numpy as np
                results = []
                q_emb = np.array(query_embedding)
                for chunk in list(self._chunks.values())[:top_k]:
                    if chunk.embedding:
                        c_emb = np.array(chunk.embedding)
                        score = np.dot(q_emb, c_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(c_emb) + 1e-9)
                    else:
                        score = 0.5
                    results.append((chunk, float(score)))
                results.sort(key=lambda x: x[1], reverse=True)
                return results
            
            def get_chunk_by_id(self, chunk_id):
                return self._chunks.get(chunk_id)
            
            def delete_chunks(self, chunk_ids):
                deleted = 0
                for cid in chunk_ids:
                    if cid in self._chunks:
                        del self._chunks[cid]
                        deleted += 1
                return deleted
            
            def update_chunk(self, chunk_id, new_embedding, new_text, new_metadata):
                if chunk_id in self._chunks:
                    chunk = self._chunks[chunk_id]
                    chunk.text = new_text
                    chunk.embedding = new_embedding
                    chunk.metadata = new_metadata or {}
                    return True
                return False
            
            def get_stats(self):
                return {"total_chunks": len(self._chunks), "type": "mock"}
            
            def health_check(self):
                return {"healthy": True, "type": "mock"}
            
            def optimize_index(self):
                pass
        
        return MockVectorStore()

    def seed_mock_data(self, tier: str, documents: List[Dict[str, Any]]) -> int:
        """Seed adapter with mock data for testing."""
        from datetime import datetime
        chunks = []
        for doc in documents:
            chunk = VectorChunk(
                chunk_id=doc.get("chunk_id", doc.get("id", "")),
                doc_id=doc.get("doc_id", ""),
                text=doc.get("text", ""),
                embedding=[],  # Will be encoded below
                metadata=doc.get("metadata", {}),
                modality=doc.get("modality", "text_native"),
                page_number=doc.get("page_number", 0),
                chunk_index=doc.get("chunk_index", 0),
                created_at=datetime.now()
            )
            chunks.append(chunk)
        return self.add_chunks(chunks)

    def add_chunks(self, chunks: List[VectorChunk]) -> int:
        """
        Adds document chunks to the index.

        Args:
            chunks: List of vectorized document chunks.

        Returns:
            int: Number of chunks successfully added.
        """
        if not chunks:
            return 0

        start_time = time.time()
        added_count = 0

        try:
            # 1. Batch encode vectors (if not already encoded)
            chunks_to_encode = [c for c in chunks if not c.embedding or len(c.embedding) == 0]

            if chunks_to_encode:
                texts = [c.text for c in chunks_to_encode]
                embeddings = self.embedding_engine.encode_batch(texts)

                for chunk, embedding in zip(chunks_to_encode, embeddings):
                    if hasattr(embedding, "tolist"):
                        embedding = embedding.tolist()
                    chunk.embedding = embedding

            # 2. Add to vector store
            vector_count = self.vector_store.add_chunks(chunks)
            added_count += vector_count

            # 3. Add to BM25 index
            bm25_docs = [{
                'id': chunk.chunk_id,
                'text': chunk.text,
                'metadata': chunk.metadata
            } for chunk in chunks]

            bm25_count = self.bm25_store.add_documents(bm25_docs)
            added_count += bm25_count
            
            # Auto-save BM25 index
            try:
                bm25_path = get_config().paths.bm25_index_file
                self.bm25_store.save(bm25_path)
            except Exception as e:
                logger.warning(f"Failed to auto-save BM25 index: {e}")

            processing_time = time.time() - start_time
            logger.info(f"Added {added_count} chunks to index in {processing_time:.2f}s")

            return added_count

        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            raise RetrievalFailedException(f"Index addition failed: {str(e)}")

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        query_profile: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Executes hybrid retrieval.

        Args:
            query: The query string.
            top_k: Number of results to return.
            filters: Metadata filtering conditions.
            query_profile: Query features for weight adjustment.

        Returns:
            List[RetrievalResult]: List of retrieval results.
        """
        start_time = time.time()
        self._performance_stats["total_queries"] += 1

        try:
            top_k = top_k or self.config.final_top_k

            # 1. Check cache first
            cache_key = f"{query}_{top_k}_{str(filters)}"
            if cache_key in self._query_cache:
                self._performance_stats["cache_hits"] += 1
                return self._query_cache[cache_key]

            # 1. Dense retrieval (BGE-M3 vectors)
            dense_start = time.time()
            query_embedding = self.embedding_engine.encode(query)
            if hasattr(query_embedding, "tolist"):
                query_embedding = query_embedding.tolist()
            dense_results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=self.config.dense_top_k,
                filters=filters,
                use_hybrid=False
            )
            dense_time = time.time() - dense_start
            self._performance_stats["avg_dense_time"] = (
                self._performance_stats["avg_dense_time"] * 0.9 + dense_time * 0.1
            )

            # 2. Sparse retrieval (BM25)
            sparse_start = time.time()
            sparse_results = self.bm25_store.search(
                query=query,
                top_k=self.config.sparse_top_k,
                filters=filters
            )
            sparse_time = time.time() - sparse_start
            self._performance_stats["avg_sparse_time"] = (
                self._performance_stats["avg_sparse_time"] * 0.9 + sparse_time * 0.1
            )

            # 3. Hybrid result fusion
            fusion_start = time.time()
            hybrid_results = self._fuse_results(
                dense_results=dense_results,
                sparse_results=sparse_results,
                query=query,
                filters=filters,
                query_profile=query_profile
            )
            fusion_time = time.time() - fusion_start
            self._performance_stats["avg_fusion_time"] = (
                self._performance_stats["avg_fusion_time"] * 0.9 + fusion_time * 0.1
            )

            # 4. P0: BGE-Reranker reranking - MANDATORY (fail-closed if empty)
            rerank_start = time.time()
            if len(hybrid_results) == 0:
                logger.warning("No candidates for reranking - fail-closed")
                raise RetrievalFailedException(query, "No candidates available for reranking")
            
            candidates_for_rerank = [
                {
                    "id": r.chunk.chunk_id,
                    "text": r.chunk.text,
                    "chunk": r.chunk
                }
                for r in hybrid_results
            ]
            
            # P0: Reranker MUST execute - no bypass
            reranked = self.reranker.rerank(
                query=query,
                candidates=candidates_for_rerank,
                top_k=min(len(candidates_for_rerank), top_k),
                return_scores=True
            )

            reranked_candidates, rerank_scores = reranked
            final_results = []
            for i, (cand, score) in enumerate(zip(reranked_candidates, rerank_scores)):
                chunk = cand.get("chunk")
                final_results.append(RetrievalResult(
                    chunk=chunk,
                    score=score,
                    rank=i + 1,
                    retrieval_type="reranked",
                    metadata={
                        "chunk_id": chunk.chunk_id,
                        "original_score": hybrid_results[i].score if i < len(hybrid_results) else 0.0,
                        "rerank_score": score,
                        "bbox": chunk.metadata.get("bbox") if chunk.metadata else None,
                        "page_number": chunk.metadata.get("page_number") if chunk.metadata else None,
                        "document_group_id": chunk.metadata.get("document_group_id") if chunk.metadata else None,
                        "version_tag": chunk.metadata.get("version_tag") if chunk.metadata else None
                    }
                ))

            rerank_time = time.time() - rerank_start
            self._performance_stats["avg_rerank_time"] = (
                self._performance_stats["avg_rerank_time"] * 0.9 + rerank_time * 0.1
            )

            # Cache results
            self._query_cache[cache_key] = final_results

            total_time = time.time() - start_time
            logger.info(
                f"Hybrid retrieval completed: {len(final_results)} results in {total_time:.3f}s "
                f"(dense: {dense_time:.3f}s, sparse: {sparse_time:.3f}s, fusion: {fusion_time:.3f}s)"
            )

            return final_results

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            raise RetrievalFailedException(f"Retrieval failed: {str(e)}")

    def search(self, request: RetrievalRequest) -> List[RawCandidate]:
        """
        Execute retrieval for a single route (for MultiRouteRecall).
        """
        query_embedding = self.embedding_engine.encode(request.query)
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        candidates: List[RawCandidate] = []

        if request.strategy == RetrievalStrategy.SPARSE:
            sparse_results = self.bm25_store.search(
                query=request.query,
                top_k=request.top_k,
                filters=request.filters
            )
            for doc, score in sparse_results:
                candidates.append(RawCandidate(
                    chunk_id=doc.get("id", ""),
                    evidence_id=doc.get("id", ""),
                    doc_id=doc.get("metadata", {}).get("doc_id", ""),
                    text=doc.get("text", ""),
                    tier=request.tier,
                    strategy=request.strategy,
                    sparse_score=score,
                    metadata=doc.get("metadata", {})
                ))
            return candidates

        if request.strategy == RetrievalStrategy.DENSE:
            dense_results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=request.top_k,
                filters=request.filters,
                use_hybrid=False
            )
        else:
            dense_results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=request.top_k,
                filters=request.filters,
                query_text=request.query,
                use_hybrid=True
            )

        for chunk, score in dense_results:
            candidates.append(RawCandidate(
                chunk_id=chunk.chunk_id,
                evidence_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                text=chunk.text,
                tier=request.tier,
                strategy=request.strategy,
                dense_score=score,
                metadata=chunk.metadata
            ))

        return candidates

    def _fuse_results(
        self,
        dense_results: List[Tuple[VectorChunk, float]],
        sparse_results: List[Tuple[Dict[str, Any], float]],
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        query_profile: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Fuse dense and sparse retrieval results.

        Implements multiple fusion strategies:
        1. Weighted Sum
        2. RRF (Reciprocal Rank Fusion)
        3. Learning-to-Rank (future)
        """
        result_map = {}
        dense_ranks = {chunk.chunk_id: idx + 1 for idx, (chunk, _) in enumerate(dense_results)}
        sparse_ranks = {doc.get("id", ""): idx + 1 for idx, (doc, _) in enumerate(sparse_results)}

        for chunk, score in dense_results:
            chunk_id = chunk.chunk_id
            result_map[chunk_id] = {
                "chunk": chunk,
                "dense_score": score * self.config.dense_weight,
                "sparse_score": 0.0,
                "dense_rank": dense_ranks.get(chunk_id, float("inf")),
                "sparse_rank": float("inf")
            }

        for doc, score in sparse_results:
            chunk_id = doc.get("id", "")
            if chunk_id in result_map:
                result_map[chunk_id]["sparse_score"] = score * self.config.sparse_weight
                result_map[chunk_id]["sparse_rank"] = sparse_ranks.get(chunk_id, float("inf"))
            else:
                chunk_data = self.vector_store.get_chunk_by_id(chunk_id)
                if chunk_data:
                    result_map[chunk_id] = {
                        "chunk": chunk_data,
                        "dense_score": 0.0,
                        "sparse_score": score * self.config.sparse_weight,
                        "dense_rank": float("inf"),
                        "sparse_rank": sparse_ranks.get(chunk_id, float("inf"))
                    }

        # 计算融合分数
        fused_results = []
        for chunk_id, data in result_map.items():
            chunk = data['chunk']

            if self.config.fusion_method == "weighted_sum":
                # Weighted sum
                final_score = data['dense_score'] + data['sparse_score']

                # Metadata boosting
                if self.config.enable_metadata_filter and filters:
                    metadata_boost = self._calculate_metadata_boost(chunk, filters)
                    final_score *= metadata_boost

            elif self.config.fusion_method == "rrf":
                # RRF fusion
                dense_rank = data.get("dense_rank", float("inf"))
                sparse_rank = data.get("sparse_rank", float("inf"))

                k = 60  # RRF constant
                rrf_score = 0
                if dense_rank != float('inf'):
                    rrf_score += 1 / (k + dense_rank)
                if sparse_rank != float('inf'):
                    rrf_score += 1 / (k + sparse_rank)
                final_score = rrf_score

            else:
                # Default weighted sum
                final_score = data['dense_score'] + data['sparse_score']

            fused_results.append({
                'chunk_id': chunk_id,
                'chunk': chunk,
                'score': final_score,
                'retrieval_type': self._determine_retrieval_type(data)
            })

        # 按分数排序
        fused_results.sort(key=lambda x: x['score'], reverse=True)

        # 转换为RetrievalResult格式
        retrieval_results = []
        for rank, result in enumerate(fused_results, 1):
            retrieval_results.append(RetrievalResult(
                chunk=result['chunk'],
                score=result['score'],
                rank=rank,
                retrieval_type=result['retrieval_type'],
                metadata={
                    'chunk_id': result['chunk_id'],
                    'fusion_method': self.config.fusion_method
                }
            ))

        return retrieval_results

    def _determine_retrieval_type(self, data: Dict[str, Any]) -> str:
        """Determine retrieval type."""
        dense_score = data.get('dense_score', 0)
        sparse_score = data.get('sparse_score', 0)

        if dense_score > 0 and sparse_score > 0:
            return "hybrid"
        elif dense_score > 0:
            return "dense"
        elif sparse_score > 0:
            return "sparse"
        else:
            return "unknown"

    def _calculate_metadata_boost(self, chunk: VectorChunk, filters: Dict[str, Any]) -> float:
        """Calculate metadata boost factor."""
        boost = 1.0

        # Check document type match
        doc_type_filter = filters.get('doc_type')
        if doc_type_filter and chunk.metadata.get('doc_type') == doc_type_filter:
            boost *= self.config.metadata_boost_factor

        # Check date range match
        date_filter = filters.get('date_range')
        if date_filter and self._is_date_in_range(chunk.metadata.get('created_at'), date_filter):
            boost *= 1.1

        # Check page number relevance
        page_filter = filters.get('page_range')
        if page_filter and self._is_page_in_range(chunk.page_number, page_filter):
            boost *= 1.05

        return boost

    def _is_date_in_range(self, date_str: Optional[str], date_range: Dict[str, str]) -> bool:
        """Check if date is in range."""
        if not date_str:
            return False

        try:
            from datetime import datetime
            chunk_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            start_date = datetime.fromisoformat(date_range.get('start', '1900-01-01'))
            end_date = datetime.fromisoformat(date_range.get('end', '2100-01-01'))

            return start_date <= chunk_date <= end_date
        except:
            return False

    def _is_page_in_range(self, page_num: int, page_range: Dict[str, int]) -> bool:
        """Check if page is in range."""
        start_page = page_range.get('start', 0)
        end_page = page_range.get('end', float('inf'))

        return start_page <= page_num <= end_page

    def delete_chunks(self, chunk_ids: List[str]) -> int:
        """
        Delete specified document chunks.

        Args:
            chunk_ids: List of chunk IDs to delete.

        Returns:
            int: Number of chunks successfully deleted.
        """
        try:
            # Delete from vector store
            vector_deleted = self.vector_store.delete_chunks(chunk_ids)

            # Delete from BM25 index
            bm25_deleted = self.bm25_store.delete_documents(chunk_ids)

            logger.info(f"Deleted {vector_deleted} chunks from vector store, {bm25_deleted} from BM25")

            return min(vector_deleted, bm25_deleted)  # Return confirmed deletion count

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            return 0

    def update_chunk(self, chunk_id: str, new_text: str, new_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update document chunk content.

        Args:
            chunk_id: Chunk ID.
            new_text: New text content.
            new_metadata: New metadata.

        Returns:
            bool: Whether update was successful.
        """
        try:
            # Re-encode vector
            new_embedding = self.embedding_engine.encode(new_text)

            # Update vector store
            success = self.vector_store.update_chunk(
                chunk_id=chunk_id,
                new_embedding=new_embedding,
                new_text=new_text,
                new_metadata=new_metadata
            )

            if success:
                # Update BM25 index
                self.bm25_store.update_document(
                    doc_id=chunk_id,
                    new_text=new_text,
                    new_metadata=new_metadata or {}
                )

            return success

        except Exception as e:
            logger.error(f"Failed to update chunk {chunk_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        try:
            vector_stats = self.vector_store.get_stats()
            bm25_stats = self.bm25_store.get_stats()

            return {
                "vector_store": vector_stats,
                "bm25_store": bm25_stats,
                "performance": self._performance_stats.copy(),
                "cache_size": len(self._query_cache),
                "config": {
                    "dense_weight": self.config.dense_weight,
                    "sparse_weight": self.config.sparse_weight,
                    "fusion_method": self.config.fusion_method,
                    "final_top_k": self.config.final_top_k
                }
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def get_document_count(self) -> Dict[str, int]:
        """Get document counts by tier."""
        counts = {"base": 0, "micro": 0, "macro": 0}
        
        try:
            # Handle MockVectorStore for tests
            if getattr(self, "_using_mock_store", False) and hasattr(self.vector_store, "_chunks"):
                for chunk in self.vector_store._chunks.values():
                    tier = getattr(chunk, "tier", "base")
                    counts[tier] = counts.get(tier, 0) + 1
                return counts
                
            # Handle PostgreSQLVectorStore
            if hasattr(self.vector_store, "get_counts_by_tier"):
                return self.vector_store.get_counts_by_tier()
                
            # Fallback
            stats = self.vector_store.get_stats()
            if "tier_counts" in stats:
                return stats["tier_counts"]
                
            # If total available, assume base
            if "total_chunks" in stats:
                counts["base"] = stats["total_chunks"]
                
            return counts
        except Exception as e:
            logger.error(f"Failed to get document counts: {e}")
            return counts

    def clear_cache(self):
        """Clear query cache."""
        self._query_cache.clear()
        logger.info("Query cache cleared")

    def optimize_index(self):
        """Optimize index performance."""
        try:
            # Optimize vector index
            self.vector_store.optimize_index()

            # Optimize BM25 index
            self.bm25_store.optimize_index()

            logger.info("Index optimization completed")

        except Exception as e:
            logger.error(f"Index optimization failed: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Health check."""
        health = {
            "overall_status": "healthy",
            "components": {},
            "issues": []
        }

        # Check vector store
        try:
            vector_health = self.vector_store.health_check()
            health["components"]["vector_store"] = vector_health
            if not vector_health.get("healthy", False):
                health["issues"].append("Vector store unhealthy")
        except Exception as e:
            health["components"]["vector_store"] = {"healthy": False, "error": str(e)}
            health["issues"].append(f"Vector store check failed: {e}")

        # Check BM25 store
        try:
            bm25_health = self.bm25_store.health_check()
            health["components"]["bm25_store"] = bm25_health
            if not bm25_health.get("healthy", False):
                health["issues"].append("BM25 store unhealthy")
        except Exception as e:
            health["components"]["bm25_store"] = {"healthy": False, "error": str(e)}
            health["issues"].append(f"BM25 store check failed: {e}")

        # Check embedding engine
        try:
            embedding_health = self.embedding_engine.health_check()
            health["components"]["embedding_engine"] = embedding_health
            if not embedding_health.get("healthy", False):
                health["issues"].append("Embedding engine unhealthy")
        except Exception as e:
            health["components"]["embedding_engine"] = {"healthy": False, "error": str(e)}
            health["issues"].append(f"Embedding engine check failed: {e}")

        # 总体状态
        if health["issues"]:
            health["overall_status"] = "unhealthy"

        return health
