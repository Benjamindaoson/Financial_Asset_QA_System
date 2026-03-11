"""Hybrid retrieval pipeline combining lexical, BM25, and vector retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app.config import settings
from app.models import Document, KnowledgeResult
from app.rag.pipeline import RAGPipeline


class HybridRAGPipeline(RAGPipeline):
    """Hybrid retrieval pipeline with weighted fusion and optional reranking."""

    def __init__(self):
        super().__init__()
        self.bm25_index = None
        self.corpus_texts: List[str] = []
        self.corpus_ids: List[str] = []
        self._build_bm25_from_chunks()

    @staticmethod
    def _bm25_tokenize(text: str) -> List[str]:
        tokens = [token.strip().lower() for token in jieba.cut(text) if token and token.strip()]
        return [token for token in tokens if len(token) >= 2]

    def _build_bm25_from_chunks(self) -> None:
        if not self.knowledge_chunks:
            return
        documents = [item["content"] for item in self.knowledge_chunks]
        doc_ids = [item["chunk_id"] for item in self.knowledge_chunks]
        self.build_bm25_index(documents, doc_ids)

    def build_bm25_index(self, documents: List[str], doc_ids: List[str]):
        tokenized_corpus = [self._bm25_tokenize(doc) for doc in documents]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        self.corpus_texts = documents
        self.corpus_ids = doc_ids

    def _bm25_search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        if not self.bm25_index:
            return []

        query_tokens = self._bm25_tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25_index.get_scores(query_tokens)
        if len(scores) == 0:
            return []

        max_score = max(float(score) for score in scores) or 1.0
        top_indices = np.argsort(scores)[-top_k:][::-1]
        results: List[Dict[str, Any]] = []
        for idx in top_indices:
            raw_score = float(scores[idx])
            if raw_score <= 0:
                continue
            chunk = self.chunk_map.get(self.corpus_ids[idx])
            if not chunk:
                continue
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "title": chunk["title"],
                    "section": chunk["section"],
                    "content": chunk["content"],
                    "score": round(raw_score / max_score, 4),
                    "raw_score": raw_score,
                    "retrieval_stage": "bm25",
                    "metadata": {"order": chunk["order"]},
                    "rank": len(results) + 1,
                }
            )
        return results

    def _rrf_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        if not vector_results and not bm25_results:
            return []

        doc_scores: Dict[str, Dict[str, Any]] = {}
        for result in vector_results:
            doc_id = result["doc_id"]
            rank = result["rank"]
            rrf_score = 1.0 / (k + rank)
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "doc_id": doc_id,
                    "text": result["text"],
                    "vector_score": result.get("score", 0.0),
                    "bm25_score": 0.0,
                    "rrf_score": 0.0,
                }
            doc_scores[doc_id]["rrf_score"] += rrf_score

        for result in bm25_results:
            doc_id = result["doc_id"]
            rank = result["rank"]
            rrf_score = 1.0 / (k + rank)
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "doc_id": doc_id,
                    "text": result["text"],
                    "vector_score": 0.0,
                    "bm25_score": result.get("score", 0.0),
                    "rrf_score": 0.0,
                }
            else:
                doc_scores[doc_id]["bm25_score"] = result.get("score", 0.0)
            doc_scores[doc_id]["rrf_score"] += rrf_score

        return sorted(doc_scores.values(), key=lambda item: item["rrf_score"], reverse=True)

    def _merge_candidates(
        self,
        local_candidates: List[Dict[str, Any]],
        bm25_candidates: List[Dict[str, Any]],
        vector_candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}

        def upsert(candidate: Dict[str, Any], signal: str):
            chunk_id = candidate["chunk_id"]
            target = merged.setdefault(
                chunk_id,
                {
                    "chunk_id": chunk_id,
                    "source": candidate["source"],
                    "title": candidate.get("title"),
                    "section": candidate.get("section"),
                    "content": candidate["content"],
                    "local_score": 0.0,
                    "bm25_score": 0.0,
                    "vector_score": 0.0,
                    "metadata": candidate.get("metadata", {}),
                },
            )
            target[f"{signal}_score"] = max(target[f"{signal}_score"], float(candidate.get("score", 0.0)))

        for candidate in local_candidates:
            upsert(candidate, "local")
        for candidate in bm25_candidates:
            upsert(candidate, "bm25")
        for candidate in vector_candidates:
            upsert(candidate, "vector")

        merged_results = []
        for item in merged.values():
            fused_score = (
                item["local_score"] * settings.RAG_FUSION_LOCAL_WEIGHT
                + item["bm25_score"] * settings.RAG_FUSION_BM25_WEIGHT
                + item["vector_score"] * settings.RAG_FUSION_VECTOR_WEIGHT
            )
            item["score"] = round(fused_score, 4)
            item["retrieval_stage"] = "hybrid"
            merged_results.append(item)

        merged_results.sort(key=lambda candidate: candidate["score"], reverse=True)
        return merged_results

    def _rerank_candidates(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        重排序候选文档（优化权重）

        两阶段检索策略：
        1. 召回阶段：混合检索获取候选集
        2. 精排阶段：使用 reranker 精确排序

        Args:
            query: 查询
            candidates: 候选文档列表

        Returns:
            重排序后的文档列表
        """
        if not candidates:
            return []

        try:
            # 只对 top-K 候选进行重排序（节省计算）
            top_k_for_rerank = min(len(candidates), max(settings.RAG_TOP_K * 2, 16))
            pairs = [[query, candidate["content"]] for candidate in candidates[:top_k_for_rerank]]
            scores = self._compute_rerank_scores(pairs)
        except Exception as e:
            logger.warning(f"重排序失败，使用原始排序: {e}")
            return candidates

        reranked: List[Dict[str, Any]] = []
        for index, candidate in enumerate(candidates[: len(scores)]):
            rerank_score = float(scores[index])
            fused_score = candidate["score"]

            # 优化权重：提高 reranker 权重到 60%
            # reranker 是 Cross-Encoder，对相关性判断更准确
            candidate["score"] = round(fused_score * 0.4 + rerank_score * 0.6, 4)
            candidate["retrieval_stage"] = "hybrid_rerank"
            candidate["rerank_score"] = rerank_score
            candidate["fusion_score"] = fused_score
            reranked.append(candidate)

        # 添加未重排序的文档（如果有）
        reranked.extend(candidates[len(scores):])

        # 按最终分数排序
        reranked.sort(key=lambda item: item["score"], reverse=True)

        return reranked

    def _filter_by_category(self, candidates: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
        """Filter candidates by metadata category."""
        filtered = []
        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            candidate_category = metadata.get("category", "")

            # Match category (case-insensitive, partial match)
            if category.lower() in candidate_category.lower():
                filtered.append(candidate)

        return filtered

    async def search(self, query: str, use_hybrid: bool = True, category_filter: Optional[str] = None) -> KnowledgeResult:
        """Search with optional metadata filtering."""
        local_candidates, profile = self._search_local_candidates(query, limit=settings.RAG_LEXICAL_TOP_K)

        # Apply category filter if specified
        if category_filter:
            local_candidates = self._filter_by_category(local_candidates, category_filter)

        if not use_hybrid:
            return KnowledgeResult(
                documents=[self._candidate_to_document(item) for item in local_candidates[: settings.RAG_TOP_N]],
                total_found=len(local_candidates),
                query=query,
                retrieval_meta={"strategy": "lexical_only", "category_filter": category_filter},
            )

        bm25_candidates = self._bm25_search(query, top_k=max(settings.RAG_TOP_K, settings.RAG_LEXICAL_TOP_K))
        vector_candidates = self._vector_search_candidates(query, limit=settings.RAG_VECTOR_TOP_K)

        # Apply category filter to all candidates
        if category_filter:
            bm25_candidates = self._filter_by_category(bm25_candidates, category_filter)
            vector_candidates = self._filter_by_category(vector_candidates, category_filter)

        merged_candidates = self._merge_candidates(local_candidates, bm25_candidates, vector_candidates)
        if not merged_candidates:
            return await super().search(query)

        merged_candidates = self._rerank_candidates(query, merged_candidates)
        focus_terms = self._pick_focus_terms(
            profile["query_tokens"],
            profile["matched_keywords"],
            profile["expanded_terms"],
        )

        top_score = merged_candidates[0]["score"] or 1.0
        threshold = max(0.3, top_score * 0.7)
        selected: List[Document] = []
        for candidate in merged_candidates:
            if candidate["score"] < threshold and len(selected) >= 1:
                continue

            selected.append(
                Document(
                    content=self._extract_snippet(candidate["content"], focus_terms),
                    source=candidate["source"],
                    score=float(candidate["score"]),
                    title=candidate.get("title"),
                    section=candidate.get("section"),
                    chunk_id=candidate.get("chunk_id"),
                    retrieval_stage=candidate.get("retrieval_stage"),
                    metadata={
                        "local_score": candidate.get("local_score", 0.0),
                        "bm25_score": candidate.get("bm25_score", 0.0),
                        "vector_score": candidate.get("vector_score", 0.0),
                    },
                )
            )
            if len(selected) >= settings.RAG_TOP_N:
                break

        return KnowledgeResult(
            documents=selected,
            total_found=len(merged_candidates),
            query=query,
            retrieval_meta={
                "strategy": "hybrid",
                "signals": {
                    "local": len(local_candidates),
                    "bm25": len(bm25_candidates),
                    "vector": len(vector_candidates),
                },
            },
        )

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["bm25_ready"] = self.bm25_index is not None
        status["bm25_corpus_size"] = len(self.corpus_ids)
        return status
