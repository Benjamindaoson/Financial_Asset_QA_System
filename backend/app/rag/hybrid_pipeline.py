"""Hybrid retrieval pipeline combining vector search, BM25, and diversity reranking."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app.config import settings
from app.models import Document, KnowledgeResult
from app.rag.dynamic_topk import DynamicTopKCalculator
from app.rag.mmr_reranker import MMRReranker
from app.rag.multi_query_generator import MultiQueryGenerator
from app.rag.pipeline import RAGPipeline
from app.rag.query_processor import QueryProcessor


class HybridRAGPipeline(RAGPipeline):
    """Vector + BM25 retrieval with multi-query expansion and MMR diversification."""

    def __init__(self, collection_name: str = "financial_knowledge"):
        super().__init__(collection_name=collection_name)
        self.bm25_index: Optional[BM25Okapi] = None
        self.corpus_texts: List[str] = []
        self.corpus_ids: List[str] = []
        self.corpus_sources: List[str] = []
        self.query_processor = QueryProcessor()
        self.topk_calculator = DynamicTopKCalculator(
            base_k=min(max(settings.RAG_TOP_N, 3), settings.RAG_TOP_K),
            max_k=max(settings.RAG_TOP_K, 15),
        )
        self.multi_query_generator = MultiQueryGenerator()
        self.mmr_reranker = MMRReranker()

        items = self._local_chunks if self._local_chunks else self._local_documents
        if items:
            if self._local_chunks:
                self.build_bm25_index(
                    [item["content"] for item in self._local_chunks],
                    [item["chunk_id"] for item in self._local_chunks],
                    [item["source"] for item in self._local_chunks],
                )
            else:
                self.build_bm25_index(
                    [item["content"] for item in self._local_documents],
                    [item["source"] for item in self._local_documents],
                )

    def build_bm25_index(
        self,
        documents: List[str],
        doc_ids: List[str],
        sources: Optional[List[str]] = None,
    ) -> None:
        """Build an in-memory BM25 index from local knowledge documents."""
        if not documents or not doc_ids:
            return

        tokenized_corpus = [list(jieba.cut(doc)) for doc in documents]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        self.corpus_texts = documents
        self.corpus_ids = doc_ids
        self.corpus_sources = sources or [""] * len(doc_ids)

    def _bm25_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if not self.bm25_index:
            return []

        query_tokens = list(jieba.cut(query))
        scores = self.bm25_index.get_scores(query_tokens)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        results: List[Dict[str, Any]] = []
        for idx in top_indices:
            if float(scores[idx]) <= 0:
                continue
            source = self.corpus_sources[idx] if idx < len(self.corpus_sources) else self.corpus_ids[idx]
            results.append(
                {
                    "doc_id": self.corpus_ids[idx],
                    "text": self.corpus_texts[idx],
                    "source": source,
                    "score": float(scores[idx]),
                    "rank": len(results) + 1,
                }
            )
        return results

    def _vector_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self.collection.count() == 0:
            return []

        query_embedding = self._embed_query(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        if not results["documents"] or not results["documents"][0]:
            return []

        return [
            {
                "doc_id": results["metadatas"][0][idx].get("chunk_id") or results["metadatas"][0][idx].get("source", "unknown"),
                "text": doc,
                "source": results["metadatas"][0][idx].get("source", "unknown"),
                "score": 1.0 - results["distances"][0][idx] if results["distances"] else 0.5,
                "rank": idx + 1,
            }
            for idx, doc in enumerate(results["documents"][0])
        ]

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        *,
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        fused: Dict[str, Dict[str, Any]] = {}

        for result in vector_results:
            doc = fused.setdefault(
                result["doc_id"],
                {
                    "doc_id": result["doc_id"],
                    "text": result["text"],
                    "source": result.get("source", "unknown"),
                    "rrf_score": 0.0,
                    "vector_score": 0.0,
                    "bm25_score": 0.0,
                },
            )
            doc["vector_score"] = max(doc["vector_score"], float(result["score"]))
            doc["rrf_score"] += 1.0 / (k + result["rank"])
            if result.get("source"):
                doc["source"] = result["source"]

        for result in bm25_results:
            doc = fused.setdefault(
                result["doc_id"],
                {
                    "doc_id": result["doc_id"],
                    "text": result["text"],
                    "source": result.get("source", "unknown"),
                    "rrf_score": 0.0,
                    "vector_score": 0.0,
                    "bm25_score": 0.0,
                },
            )
            doc["bm25_score"] = max(doc["bm25_score"], float(result["score"]))
            doc["rrf_score"] += 1.0 / (k + result["rank"])
            if result.get("source"):
                doc["source"] = result["source"]

        return sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)

    async def _generate_query_variants(self, query: str) -> List[str]:
        query_variants = [query]
        if settings.QUERY_REWRITE_ENABLED:
            processed = self.query_processor.process(query)
            query_variants = processed.get("expanded_queries") or [processed.get("normalized") or query]

        generated = self.multi_query_generator.generate_queries(query_variants[0], num_queries=3)
        ordered_unique: List[str] = []
        seen = set()
        for item in [*query_variants, *generated]:
            cleaned = (item or "").strip()
            if cleaned and cleaned not in seen:
                ordered_unique.append(cleaned)
                seen.add(cleaned)

        if settings.HYDE_ENABLED:
            try:
                from app.rag.hyde_generator import HyDEGenerator
                hyde = HyDEGenerator()
                hyde_doc = await hyde.generate(query)
                if hyde_doc and hyde_doc not in seen:
                    ordered_unique.append(hyde_doc)
                    seen.add(hyde_doc)
            except Exception:
                pass

        return ordered_unique[:5]

    def _collect_candidates(self, query_variants: List[str], top_k: int) -> List[Dict[str, Any]]:
        aggregated: Dict[str, Dict[str, Any]] = {}

        for variant in query_variants:
            fused = self._reciprocal_rank_fusion(
                self._vector_search(variant, top_k),
                self._bm25_search(variant, top_k),
            )
            for rank, item in enumerate(fused[:top_k], start=1):
                candidate = aggregated.setdefault(
                    item["doc_id"],
                    {
                        "doc_id": item["doc_id"],
                        "text": item["text"],
                        "source": item.get("source", "unknown"),
                        "fusion_score": 0.0,
                        "best_rank": rank,
                    },
                )
                candidate["fusion_score"] += item["rrf_score"]
                candidate["best_rank"] = min(candidate["best_rank"], rank)

        return sorted(
            aggregated.values(),
            key=lambda item: (item["fusion_score"], -item["best_rank"]),
            reverse=True,
        )

    def _rerank_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        score_threshold: float,
    ) -> List[Document]:
        pairs = [[query, candidate["text"]] for candidate in candidates]
        try:
            scores = self.reranker.compute_score(pairs, normalize=True)
        except TypeError:
            raw_scores = self.reranker.compute_score(pairs)
            if not isinstance(raw_scores, list):
                raw_scores = [raw_scores]
            scores = [1.0 / (1.0 + math.exp(-float(value))) for value in raw_scores]

        if not isinstance(scores, list):
            scores = [scores]

        ranked = []
        for idx, score in enumerate(scores):
            if float(score) < score_threshold:
                continue
            cand = candidates[idx]
            doc_id = cand["doc_id"]
            parts = doc_id.rsplit("_", 1)
            is_chunk_id = len(parts) == 2 and parts[1].isdigit()
            source = cand.get("source") or (parts[0] if is_chunk_id else doc_id)
            ranked.append(
                Document(
                    content=cand["text"],
                    source=source,
                    score=float(score),
                    chunk_id=doc_id if is_chunk_id else None,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    async def search(self, query: str, use_hybrid: bool = True) -> KnowledgeResult:
        """Keep token-match as the fast path and use grounded retrieval when needed."""
        local_result = self._search_local_documents(query)
        if local_result.documents and not use_hybrid:
            return local_result

        grounded = await self.search_grounded(query, score_threshold=settings.RAG_SCORE_THRESHOLD)
        if grounded.documents:
            return grounded
        return local_result

    async def search_grounded(
        self,
        query: str,
        score_threshold: float = 0.3,
        top_k: Optional[int] = None,
    ) -> KnowledgeResult:
        """Search with adaptive Top-K, query expansion, BM25 fusion, and MMR reranking."""
        self._ensure_models()

        if self.collection.count() == 0 and not self.bm25_index:
            return KnowledgeResult(documents=[], total_found=0)

        effective_top_k = max(top_k or self.topk_calculator.calculate_topk(query), settings.RAG_TOP_N)
        query_variants = await self._generate_query_variants(query)
        candidates = self._collect_candidates(query_variants, effective_top_k)
        if not candidates:
            return KnowledgeResult(documents=[], total_found=0)

        reranked = self._rerank_candidates(query, candidates[:effective_top_k], score_threshold)
        if not reranked:
            return KnowledgeResult(documents=[], total_found=len(candidates))

        diversified = self.mmr_reranker.rerank(
            reranked,
            top_n=settings.RAG_TOP_N,
            similarity_fn=self.mmr_reranker.cosine_similarity,
        )

        if settings.ITERATIVE_RETRIEVAL_ENABLED:
            from app.rag.iterative_retriever import IterativeRetriever
            iterative = IterativeRetriever()
            if not iterative.sufficiency_check(query, diversified):
                rewritten = iterative.rewrite_for_retrieval(query, diversified)
                r2_variants = await self._generate_query_variants(rewritten)
                r2_candidates = self._collect_candidates(r2_variants, effective_top_k)
                if r2_candidates:
                    r2_reranked = self._rerank_candidates(
                        query, r2_candidates[:effective_top_k], score_threshold
                    )
                    if r2_reranked:
                        seen_ids = {d.chunk_id for d in diversified if d.chunk_id}
                        for doc in r2_reranked:
                            if doc.chunk_id and doc.chunk_id not in seen_ids:
                                diversified.append(doc)
                                seen_ids.add(doc.chunk_id)
                        diversified = diversified[: settings.RAG_TOP_N * 2]
                        diversified = self.mmr_reranker.rerank(
                            diversified,
                            top_n=settings.RAG_TOP_N,
                            similarity_fn=self.mmr_reranker.cosine_similarity,
                        )

        return KnowledgeResult(documents=diversified, total_found=len(candidates))
