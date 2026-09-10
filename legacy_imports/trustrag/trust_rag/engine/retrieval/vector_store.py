"""
Vector Store: structured vector storage with PostgreSQL + pgvector.

Replaces JSON/FAISS with ACID-compliant vector database.
Supports hybrid search, metadata filtering, and full-text search.
"""
import logging
import json
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from trust_rag.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class VectorChunk:
    """Vector chunk with metadata."""
    chunk_id: str
    doc_id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    modality: str
    page_number: int
    chunk_index: int
    created_at: datetime


@dataclass
class SearchResult:
    """Search result with score and metadata."""
    chunk: VectorChunk
    score: float
    rank: int


class PostgreSQLVectorStore:
    """
    Production vector store using PostgreSQL + pgvector.
    Dual-track storage design: PostgreSQL as primary, FAISS as L2 cache/fallback option.

    Features:
    - ACID transactions (resolves index consistency issues)
    - Hybrid search (vector + text + metadata)
    - Metadata filtering (specialized for financial docs)
    - Full-text search (BM25)
    - HNSW index optimization
    - Dual-track fallback support
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        enable_fallback_cache: bool = True,
        cache_dir: Optional[str] = None
    ):
        self.connection_string = connection_string or self._get_connection_string()
        self.enable_fallback_cache = enable_fallback_cache
        self.cache_dir = cache_dir or get_config().paths.artifacts_dir

        # Primary database connection
        self.conn = None
        self._connection_pool = None

        # PRODUCTION: Enforcement of pgvector usage, no fallback allowed
        self.fallback_cache = None  # Production does not use local cache

        # Mandatory initialization of primary database - production requirement
        try:
            self._ensure_connection()
            self._ensure_tables()
            self._ensure_indexes()  # Production: verify index existence
            logger.info("✅ PRODUCTION: PostgreSQL + pgvector initialized with indexes")
        except Exception as e:
            logger.error(f"❌ CRITICAL: Cannot initialize pgvector: {e}")
            raise RuntimeError(f"pgvector required for production: {e}")

        # Performance statistics
        self.stats = {
            "searches": 0,
            "inserts": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "fallbacks_used": 0
        }

    def _init_fallback_cache(self):
        """Initializes FAISS L2 cache as a fallback option."""
        try:
            from trust_rag.engine.retrieval.faiss_cache import FAISSVectorCache
            self.fallback_cache = FAISSVectorCache(cache_dir=self.cache_dir)
            logger.info("FAISS fallback cache initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize fallback cache: {e}")
            self.fallback_cache = None

    def _get_connection_string(self) -> str:
        """Get PostgreSQL connection string from config."""
        config = get_config()
        return (
            f"postgresql://{config.database.user}:{config.database.password}"
            f"@{config.database.host}:{config.database.port}/{config.database.database}"
        )

    def _ensure_tables(self):
        """Create tables and indexes if they don't exist."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Enable pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # Create chunks table with vector column
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vector_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        text TEXT NOT NULL,
                        embedding vector(1024),  -- BGE-M3 dimension
                        metadata JSONB,
                        modality TEXT,
                        page_number INTEGER,
                        chunk_index INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # Create indexes for performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_vector_chunks_doc_id
                    ON vector_chunks(doc_id);
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_vector_chunks_modality
                    ON vector_chunks(modality);
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_vector_chunks_created_at
                    ON vector_chunks(created_at);
                """)

                # Vector similarity search index (HNSW for production)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS vector_chunks_embedding_idx
                    ON vector_chunks USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """)

                # Full-text search index
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_vector_chunks_text
                    ON vector_chunks USING gin(to_tsvector('english', text));
                """)

                conn.commit()

    def _get_connection(self):
        """Get database connection with connection pooling."""
        if not self.conn:
            import psycopg2
            self.conn = psycopg2.connect(self.connection_string)
        return self.conn

    def _ensure_connection(self):
        """Fail-fast connection check."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()

    def add_chunks(self, chunks: List[VectorChunk]) -> int:
        """Compatibility wrapper for adapter usage."""
        return self.insert_chunks(chunks)

    def insert_chunks(self, chunks: List[VectorChunk]) -> int:
        """
        Insert vector chunks in batch with transaction.

        Args:
            chunks: List of VectorChunk objects

        Returns:
            Number of chunks inserted
        """
        if not chunks:
            return 0

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Prepare batch insert data
                values = []
                for chunk in chunks:
                    values.append((
                        chunk.chunk_id,
                        chunk.doc_id,
                        chunk.text,
                        chunk.embedding,
                        json.dumps(chunk.metadata),
                        chunk.modality,
                        chunk.page_number,
                        chunk.chunk_index,
                        chunk.created_at
                    ))

                # Batch insert with ON CONFLICT DO UPDATE
                cur.executemany("""
                    INSERT INTO vector_chunks (
                        chunk_id, doc_id, text, embedding, metadata,
                        modality, page_number, chunk_index, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        modality = EXCLUDED.modality,
                        page_number = EXCLUDED.page_number
                """, values)

                conn.commit()
                return len(chunks)

    def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 20,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search similar vectors with dual-track fallback policy.

        Args:
            query_embedding: Query embedding vector
            limit: Maximum results to return
            threshold: Minimum similarity threshold
            filters: Metadata filters (e.g., {"modality": "table_native"})

        Returns:
            List of SearchResult objects
        """
        self.stats["searches"] += 1

        # First try primary PostgreSQL database
        try:
            results = self._search_postgres(query_embedding, limit, threshold, filters)
            if results:  # Results found
                return results

            # If primary database returns nothing, try cache
            if self.fallback_cache:
                logger.debug("Primary store returned no results, checking cache")
                self.stats["cache_hits"] += 1
                return self.fallback_cache.search_similar(query_embedding, limit, threshold, filters)

        except Exception as e:
            logger.warning(f"Primary PostgreSQL search failed: {e}, falling back to cache")
            self.stats["fallbacks_used"] += 1

            # Fallback to FAISS cache
            if self.fallback_cache:
                try:
                    return self.fallback_cache.search_similar(query_embedding, limit, threshold, filters)
                except Exception as cache_error:
                    logger.error(f"Fallback cache also failed: {cache_error}")

            # Complete failure, return empty results
            logger.error("Both primary and fallback search failed")
            return []

    def _search_postgres(
        self,
        query_embedding: List[float],
        limit: int,
        threshold: float,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """PostgreSQL primary store search implementation."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Build WHERE clause for filters
                where_clauses = []
                params = [query_embedding]

                if filters:
                    for key, value in filters.items():
                        where_clauses.append(f"metadata->>%s = %s")
                        params.extend([key, str(value)])

                where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

                # Vector similarity search with HNSW index (production optimized)
                query = f"""
                    SELECT chunk_id, doc_id, text, embedding, metadata,
                           modality, page_number, chunk_index, created_at,
                           1 - (embedding <=> %s::vector) as similarity
                    FROM vector_chunks
                    WHERE {where_clause} AND (1 - (embedding <=> %s::vector)) > %s
                    ORDER BY embedding <=> %s::vector  -- Uses HNSW index
                    LIMIT %s
                """

                params.extend([query_embedding, threshold, query_embedding, limit])

                cur.execute(query, params)

                results = []
                for row in cur.fetchall():
                    chunk = VectorChunk(
                        chunk_id=row[0],
                        doc_id=row[1],
                        text=row[2],
                        embedding=row[3],  # pgvector returns list
                        metadata=json.loads(row[4]) if row[4] else {},
                        modality=row[5],
                        page_number=row[6],
                        chunk_index=row[7],
                        created_at=row[8]
                    )
                    results.append(SearchResult(
                        chunk=chunk,
                        score=float(row[9]),  # similarity score
                        rank=len(results) + 1
                    ))

                return results

    def search_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = 20,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Hybrid search combining vector similarity and text search.

        Args:
            query_embedding: Query embedding vector
            query_text: Query text for full-text search
            limit: Maximum results to return
            vector_weight: Weight for vector similarity
            text_weight: Weight for text similarity
            filters: Metadata filters

        Returns:
            List of SearchResult objects
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Build WHERE clause for filters
                where_clauses = []
                params = [query_embedding, query_text, vector_weight, text_weight]

                if filters:
                    for key, value in filters.items():
                        where_clauses.append(f"metadata->>%s = %s")
                        params.extend([key, str(value)])

                where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

                # Hybrid search query
                query = f"""
                    SELECT chunk_id, doc_id, text, embedding, metadata,
                           modality, page_number, chunk_index, created_at,
                           (
                               %s * (1 - (embedding <=> %s::vector)) +
                               %s * ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s))
                           ) as hybrid_score
                    FROM vector_chunks
                    WHERE {where_clause}
                    ORDER BY hybrid_score DESC
                    LIMIT %s
                """

                params.append(limit)
                cur.execute(query, params)

                results = []
                for row in cur.fetchall():
                    chunk = VectorChunk(
                        chunk_id=row[0],
                        doc_id=row[1],
                        text=row[2],
                        embedding=row[3],
                        metadata=json.loads(row[4]) if row[4] else {},
                        modality=row[5],
                        page_number=row[6],
                        chunk_index=row[7],
                        created_at=row[8]
                    )
                    results.append(SearchResult(
                        chunk=chunk,
                        score=float(row[9]),  # hybrid score
                        rank=len(results) + 1
                    ))

                return results

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        query_text: Optional[str] = None,
        use_hybrid: bool = False
    ) -> List[Tuple[VectorChunk, float]]:
        """Unified search API for adapter compatibility."""
        if use_hybrid and query_text:
            results = self.search_hybrid(
                query_embedding=query_embedding,
                query_text=query_text,
                limit=top_k,
                filters=filters
            )
            return [(r.chunk, r.score) for r in results]

        results = self.search_similar(
            query_embedding=query_embedding,
            limit=top_k,
            filters=filters
        )
        return [(r.chunk, r.score) for r in results]

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all chunks for a document.

        Args:
            doc_id: Document ID to delete

        Returns:
            Number of chunks deleted
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vector_chunks WHERE doc_id = %s", (doc_id,))
                deleted_count = cur.rowcount
                conn.commit()
                return deleted_count

    def delete_chunks(self, chunk_ids: List[str]) -> int:
        """Delete chunks by chunk_id."""
        if not chunk_ids:
            return 0

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM vector_chunks WHERE chunk_id = ANY(%s)",
                    (chunk_ids,)
                )
                deleted_count = cur.rowcount
                conn.commit()
                return deleted_count

    def update_chunk(
        self,
        chunk_id: str,
        new_embedding: List[float],
        new_text: str,
        new_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a chunk's vector/text/metadata."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vector_chunks
                    SET text = %s,
                        embedding = %s,
                        metadata = %s
                    WHERE chunk_id = %s
                    """,
                    (new_text, new_embedding, json.dumps(new_metadata or {}), chunk_id)
                )
                updated = cur.rowcount > 0
                conn.commit()
                return updated

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Total chunks
                cur.execute("SELECT COUNT(*) FROM vector_chunks")
                total_chunks = cur.fetchone()[0]

                # Documents count
                cur.execute("SELECT COUNT(DISTINCT doc_id) FROM vector_chunks")
                total_docs = cur.fetchone()[0]

                # Modality distribution
                cur.execute("""
                    SELECT modality, COUNT(*) as count
                    FROM vector_chunks
                    GROUP BY modality
                    ORDER BY count DESC
                """)
                modality_stats = dict(cur.fetchall())

                return {
                    "total_chunks": total_chunks,
                    "total_documents": total_docs,
                    "modality_distribution": modality_stats,
                    "database_size": self._get_db_size()
                }

    def get_chunk_by_id(self, chunk_id: str) -> Optional[VectorChunk]:
        """Fetch a single chunk by chunk_id."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT chunk_id, doc_id, text, embedding, metadata,
                           modality, page_number, chunk_index, created_at
                    FROM vector_chunks
                    WHERE chunk_id = %s
                    LIMIT 1
                """, (chunk_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return VectorChunk(
                    chunk_id=row[0],
                    doc_id=row[1],
                    text=row[2],
                    embedding=row[3],
                    metadata=json.loads(row[4]) if row[4] else {},
                    modality=row[5],
                    page_number=row[6],
                    chunk_index=row[7],
                    created_at=row[8]
                )

    def _get_db_size(self) -> str:
        """Get database size."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                return cur.fetchone()[0]

    def _ensure_indexes(self):
        """Production requirement: Ensure all necessary indexes exist, fail-fast otherwise."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Check HNSW vector index
                cur.execute("""
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'vector_chunks'
                    AND indexname = 'vector_chunks_embedding_idx'
                """)
                if not cur.fetchone():
                    logger.error("❌ CRITICAL: HNSW vector index missing - run migrations")
                    raise RuntimeError("HNSW vector index required for production")

                # Check metadata indexes
                required_indexes = [
                    'idx_vector_chunks_doc_id',
                    'idx_vector_chunks_modality',
                    'idx_vector_chunks_created_at'
                ]

                for idx_name in required_indexes:
                    cur.execute("""
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'vector_chunks'
                        AND indexname = %s
                    """, (idx_name,))
                    if not cur.fetchone():
                        logger.error(f"❌ CRITICAL: Metadata index {idx_name} missing")
                        raise RuntimeError(f"Metadata index {idx_name} required for production")

                logger.info("✅ PRODUCTION: All vector indexes verified")

    def optimize_indexes(self):
        """Optimize vector indexes for better search performance."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("REINDEX INDEX vector_chunks_embedding_idx;")
                logger.info("Vector index optimized (HNSW)")
                conn.commit()

    def health_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            stats = self.get_stats()
            return {"healthy": True, "stats": stats}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def close(self):
        """Close database connections."""
        if self.conn:
            self.conn.close()
            self.conn = None
