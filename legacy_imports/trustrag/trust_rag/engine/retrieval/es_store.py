"""
Elasticsearch Vector Store Implementation.
Provides industrial-grade hybrid search (Dense + BM25) for TrustRAG.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from trust_rag.engine.retrieval.vector_store import VectorChunk, SearchResult

logger = logging.getLogger(__name__)

class ElasticsearchVectorStore:
    """
    Production vector store using Elasticsearch (8.0+).
    Excellent for true hybrid search (BM25 + Dense Vectors) and complex metadata filtering.
    """

    def __init__(
        self,
        host: str = "http://localhost:9200",
        index_name: str = "trust_rag_chunks",
        dim: int = 1024,
        username: str = "elastic",
        password: str = "changeme"
    ):
        self.host = host
        self.index_name = index_name
        self.dim = dim
        self.client = None
        
        try:
            from elasticsearch import Elasticsearch
            self.client = Elasticsearch(
                host,
                basic_auth=(username, password)
            )
            
            if self.client.ping():
                self._ensure_index()
                logger.info(f"✅ PRODUCTION: Elasticsearch Store initialized ({index_name})")
            else:
                logger.warning("Elasticsearch ping failed. Store unavailable.")
                self.client = None
        except ImportError:
            logger.warning("elasticsearch package not installed.")
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch: {e}")

    def _ensure_index(self):
        """Create ES index with dense_vector mappings if not exists."""
        if not self.client: return
        
        try:
            if not self.client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "chunk_id": {"type": "keyword"},
                            "doc_id": {"type": "keyword"},
                            "text": {"type": "text", "analyzer": "standard"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": self.dim,
                                "index": True,
                                "similarity": "cosine"
                            },
                            "metadata": {"type": "object"},
                            "modality": {"type": "keyword"},
                            "page_number": {"type": "integer"},
                            "chunk_index": {"type": "integer"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
                self.client.indices.create(index=self.index_name, body=mapping)
                logger.info(f"Created Elasticsearch index {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to create ES index: {e}")

    def add_chunks(self, chunks: List[VectorChunk]) -> int:
        return self.insert_chunks(chunks)

    def insert_chunks(self, chunks: List[VectorChunk]) -> int:
        from elasticsearch import helpers
        if not self.client or not chunks: return 0
        
        actions = []
        for chunk in chunks:
            action = {
                "_index": self.index_name,
                "_id": chunk.chunk_id,
                "_source": {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "embedding": chunk.embedding,
                    "metadata": chunk.metadata,
                    "modality": chunk.modality,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "created_at": chunk.created_at.isoformat() if chunk.created_at else None
                }
            }
            actions.append(action)
            
        try:
            success, _ = helpers.bulk(self.client, actions, refresh=True)
            return success
        except Exception as e:
            logger.error(f"Elasticsearch insertion failed: {e}")
            return 0

    def _build_filter(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert basic dictionary filters to ES term queries."""
        must_filters = []
        for k, v in filters.items():
            must_filters.append({"term": {f"metadata.{k}": v}})
        return must_filters

    def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 20,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        if not self.client: return []
        
        try:
            query = {
                "knn": {
                    "field": "embedding",
                    "query_vector": query_embedding,
                    "k": limit,
                    "num_candidates": limit * 5
                }
            }
            
            if filters:
                query["knn"]["filter"] = self._build_filter(filters)
                
            res = self.client.search(
                index=self.index_name,
                body=query,
                size=limit,
                _source=["chunk_id", "doc_id", "text", "metadata", "modality"]
            )
            
            ret = []
            for hit in res.get("hits", {}).get("hits", []):
                score = hit.get("_score", 0.0)
                if score < threshold: continue
                
                src = hit["_source"]
                chunk = VectorChunk(
                    chunk_id=src.get("chunk_id"),
                    doc_id=src.get("doc_id"),
                    text=src.get("text"),
                    embedding=[],
                    metadata=src.get("metadata", {}),
                    modality=src.get("modality"),
                    page_number=0, chunk_index=0, created_at=datetime.now()
                )
                ret.append(SearchResult(chunk=chunk, score=score, rank=len(ret)+1))
            return ret
        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            return []

    def search_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = 20,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        if not self.client: return []
        
        try:
            body = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"text": {"query": query_text, "boost": text_weight}}}
                        ]
                    }
                },
                "knn": {
                    "field": "embedding",
                    "query_vector": query_embedding,
                    "k": limit,
                    "num_candidates": limit * 5,
                    "boost": vector_weight
                },
                "size": limit,
                "_source": ["chunk_id", "doc_id", "text", "metadata", "modality"]
            }
            
            if filters:
                body["knn"]["filter"] = self._build_filter(filters)
                body["query"]["bool"]["filter"] = self._build_filter(filters)
                
            res = self.client.search(index=self.index_name, body=body)
            
            ret = []
            for hit in res.get("hits", {}).get("hits", []):
                src = hit["_source"]
                chunk = VectorChunk(
                    chunk_id=src.get("chunk_id"),
                    doc_id=src.get("doc_id"),
                    text=src.get("text"),
                    embedding=[],
                    metadata=src.get("metadata", {}),
                    modality=src.get("modality"),
                    page_number=0, chunk_index=0, created_at=datetime.now()
                )
                ret.append(SearchResult(chunk=chunk, score=hit.get("_score", 0.0), rank=len(ret)+1))
            return ret
        except Exception as e:
            logger.error(f"Elasticsearch hybrid search failed: {e}")
            return []

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        query_text: Optional[str] = None,
        use_hybrid: bool = False
    ) -> List[Tuple[VectorChunk, float]]:
        if use_hybrid and query_text:
            results = self.search_hybrid(query_embedding, query_text, top_k, filters=filters)
        else:
            results = self.search_similar(query_embedding, top_k, filters=filters)
        return [(r.chunk, r.score) for r in results]

    def delete_by_doc_id(self, doc_id: str) -> int:
        if not self.client: return 0
        try:
            q = {"query": {"term": {"doc_id": doc_id}}}
            res = self.client.delete_by_query(index=self.index_name, body=q)
            return res.get("deleted", 0)
        except Exception as e:
            logger.error(f"ES deletion failed: {e}")
            return 0

    def delete_chunks(self, chunk_ids: List[str]) -> int:
        if not self.client or not chunk_ids: return 0
        try:
            q = {"query": {"terms": {"chunk_id": chunk_ids}}}
            res = self.client.delete_by_query(index=self.index_name, body=q)
            return res.get("deleted", 0)
        except Exception:
            return 0

    def get_stats(self) -> Dict[str, Any]:
        if not self.client: return {"status": "uninitialized"}
        try:
            count = self.client.count(index=self.index_name)
            return {"total_chunks": count.get("count", 0), "engine": "Elasticsearch"}
        except Exception:
            return {}

    def get_chunk_by_id(self, chunk_id: str) -> Optional[VectorChunk]:
        if not self.client: return None
        try:
            res = self.client.get(index=self.index_name, id=chunk_id)
            src = res["_source"]
            return VectorChunk(
                chunk_id=src.get("chunk_id"),
                doc_id=src.get("doc_id"),
                text=src.get("text"),
                embedding=[], metadata=src.get("metadata", {}), modality=src.get("modality"),
                page_number=0, chunk_index=0, created_at=datetime.now()
            )
        except Exception:
            return None
