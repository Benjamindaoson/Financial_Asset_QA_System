"""Hybrid retrieval pipeline combining lexical, BM25, and vector retrieval."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app.config import settings
from app.models import Document, KnowledgeResult
from app.rag.pipeline import RAGPipeline
from app.rag.semantic_chunker import SemanticChunker

logger = logging.getLogger(__name__)


class HybridRAGPipeline(RAGPipeline):
    """Hybrid retrieval pipeline with weighted fusion and optional reranking."""

    def __init__(self):
        super().__init__()
        try:
            self.semantic_chunker = SemanticChunker()
        except Exception:
            self.semantic_chunker = None
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
                    "metadata": {**chunk.get("metadata", {}), "order": chunk["order"]},
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
        signal_lists = [("vector", vector_results), ("bm25", bm25_results)]

        for signal_name, results in signal_lists:
            ranked_results = sorted(results, key=lambda item: item.get("score", 0.0), reverse=True)
            for rank, result in enumerate(ranked_results, start=1):
                doc_id = result.get("chunk_id") or result.get("doc_id")
                if not doc_id:
                    continue
                rrf_score = 1.0 / (k + rank)
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "chunk_id": doc_id,
                        "doc_id": doc_id,
                        "source": result.get("source", "unknown"),
                        "title": result.get("title"),
                        "section": result.get("section"),
                        "content": result.get("content") or result.get("text", ""),
                        "metadata": dict(result.get("metadata", {})),
                        "local_score": 0.0,
                        "bm25_score": 0.0,
                        "vector_score": 0.0,
                        "rrf_score": 0.0,
                    }
                doc_scores[doc_id][f"{signal_name}_score"] = max(
                    doc_scores[doc_id].get(f"{signal_name}_score", 0.0),
                    float(result.get("score", 0.0)),
                )
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

        rrf_seed = self._rrf_fusion(
            local_candidates + vector_candidates,
            bm25_candidates,
        )
        rrf_scores = {item["chunk_id"]: item["rrf_score"] for item in rrf_seed}
        top_rrf = max(rrf_scores.values()) if rrf_scores else 1.0
        merged_results = []
        for item in merged.values():
            weighted_score = (
                item["local_score"] * settings.RAG_FUSION_LOCAL_WEIGHT
                + item["bm25_score"] * settings.RAG_FUSION_BM25_WEIGHT
                + item["vector_score"] * settings.RAG_FUSION_VECTOR_WEIGHT
            )
            metadata = item.get("metadata", {})
            structural_bonus = 0.0
            if metadata.get("chunk_type") == "table":
                structural_bonus += 0.05
            if metadata.get("source_type") == "report":
                structural_bonus += 0.03
            item["rrf_score"] = round(rrf_scores.get(item["chunk_id"], 0.0), 6)
            item["weighted_score"] = round(weighted_score + structural_bonus, 4)
            normalized_rrf = item["rrf_score"] / top_rrf if top_rrf else 0.0
            item["score"] = round(normalized_rrf * 0.7 + item["weighted_score"] * 0.3, 4)
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

    def _apply_definition_bias(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        profile = self._build_query_profile(query)
        if not profile.get("prefers_definition") or not profile.get("canonical_concepts"):
            return candidates

        formula_intent = bool(profile.get("formula_intent"))
        boosted: List[Dict[str, Any]] = []
        for candidate in candidates:
            item = dict(candidate)
            score = float(item.get("score", 0.0))
            source = item.get("source", "")
            section = (item.get("section") or "").lower()
            metadata = dict(item.get("metadata", {}))
            bonus = 0.0

            if source == "core_finance_metrics.md":
                bonus += 0.68
            elif source in {"valuation_metrics.md", "基本面分析.md"}:
                bonus += 0.08

            if "定义" in section:
                bonus += 0.12
            elif formula_intent and any(token in section for token in ("公式", "计算")):
                bonus += 0.08
            elif any(token in section for token in ("公式", "计算")):
                bonus += 0.01
            elif "使用提示" in section:
                bonus -= 0.01

            if metadata.get("source_type") == "textbook":
                bonus -= 0.04

            if "fcf" in profile.get("canonical_concepts", set()) and any(token in section for token in ("fcff", "fcfe")):
                bonus -= 0.05

            item["score"] = round(score + bonus, 4)
            boosted.append(item)

        boosted.sort(key=lambda item: item["score"], reverse=True)
        return boosted

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

    @staticmethod
    def _metadata_matches(metadata: Dict[str, Any], metadata_filter: Dict[str, Any]) -> bool:
        for key, expected in metadata_filter.items():
            if expected in (None, "", [], ()):
                continue
            actual = metadata.get(key)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
                continue
            if key == "date" and isinstance(actual, str) and isinstance(expected, str):
                if not actual.startswith(expected):
                    return False
                continue
            if actual != expected:
                return False
        return True

    def _filter_by_metadata(self, candidates: List[Dict[str, Any]], metadata_filter: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not metadata_filter:
            return candidates
        return [candidate for candidate in candidates if self._metadata_matches(candidate.get("metadata", {}), metadata_filter)]

    @staticmethod
    def _combine_variant_candidates(candidate_groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for candidates in candidate_groups:
            for candidate in candidates:
                chunk_id = candidate["chunk_id"]
                current = merged.get(chunk_id)
                if current is None or float(candidate.get("score", 0.0)) > float(current.get("score", 0.0)):
                    merged[chunk_id] = dict(candidate)
        results = list(merged.values())
        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return results

    async def search(
        self,
        query: str,
        use_hybrid: bool = True,
        category_filter: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeResult:
        """Search with optional metadata filtering."""
        query_variants = self.generate_query_variants(query) if settings.RAG_USE_QUERY_REWRITING else [query]
        local_groups: List[List[Dict[str, Any]]] = []
        bm25_groups: List[List[Dict[str, Any]]] = []
        vector_groups: List[List[Dict[str, Any]]] = []
        profile = None

        for variant in query_variants:
            local_candidates, profile = self._search_local_candidates(variant, limit=settings.RAG_LEXICAL_TOP_K)
            local_groups.append(local_candidates)
            if use_hybrid:
                bm25_groups.append(self._bm25_search(variant, top_k=max(settings.RAG_TOP_K, settings.RAG_LEXICAL_TOP_K)))
                vector_groups.append(self._vector_search_candidates(variant, limit=settings.RAG_VECTOR_TOP_K))

        local_candidates = self._combine_variant_candidates(local_groups)

        # Apply category filter if specified
        if category_filter:
            local_candidates = self._filter_by_category(local_candidates, category_filter)
        local_candidates = self._filter_by_metadata(local_candidates, metadata_filter)

        if not use_hybrid:
            return KnowledgeResult(
                documents=[self._candidate_to_document(item) for item in local_candidates[: settings.RAG_TOP_N]],
                total_found=len(local_candidates),
                query=query,
                retrieval_meta={
                    "strategy": "lexical_only",
                    "category_filter": category_filter,
                    "metadata_filter": metadata_filter,
                    "query_variants": query_variants,
                },
            )

        bm25_candidates = self._combine_variant_candidates(bm25_groups)
        vector_candidates = self._combine_variant_candidates(vector_groups)

        # Apply category filter to all candidates
        if category_filter:
            bm25_candidates = self._filter_by_category(bm25_candidates, category_filter)
            vector_candidates = self._filter_by_category(vector_candidates, category_filter)
        bm25_candidates = self._filter_by_metadata(bm25_candidates, metadata_filter)
        vector_candidates = self._filter_by_metadata(vector_candidates, metadata_filter)

        merged_candidates = self._merge_candidates(local_candidates, bm25_candidates, vector_candidates)
        if not merged_candidates:
            return await super().search(query)

        merged_candidates = self._rerank_candidates(query, merged_candidates)
        merged_candidates = self._apply_definition_bias(query, merged_candidates)
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
                        **candidate.get("metadata", {}),
                        "local_score": candidate.get("local_score", 0.0),
                        "bm25_score": candidate.get("bm25_score", 0.0),
                        "vector_score": candidate.get("vector_score", 0.0),
                        "rrf_score": candidate.get("rrf_score", 0.0),
                        "weighted_score": candidate.get("weighted_score", 0.0),
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
                "query_variants": query_variants,
                "metadata_filter": metadata_filter,
            },
        )

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["bm25_ready"] = self.bm25_index is not None
        status["bm25_corpus_size"] = len(self.corpus_ids)
        return status
