"""Confidence scorer for retrieval quality."""

from __future__ import annotations

from typing import Iterable, List

import jieba

from app.models import Document


class ConfidenceScorer:
    """Quantify retrieval quality for knowledge-grounded answers."""

    def __init__(self):
        self.weights = {
            "retrieval": 0.35,
            "gap": 0.2,
            "coverage": 0.25,
            "support": 0.2,
        }
        self.stopwords = {
            "的",
            "了",
            "是",
            "在",
            "有",
            "和",
            "与",
            "及",
            "对",
            "吗",
            "呢",
            "啊",
            "什么",
            "如何",
            "请问",
            "一下",
        }

    def calculate(self, query: str, documents: List[Document]) -> float:
        if not documents:
            return 0.0

        top_score = self._clamp(documents[0].score)
        score_gap = 0.0
        if len(documents) >= 2:
            score_gap = self._clamp(documents[0].score - documents[1].score)

        top_coverage = self._calculate_coverage(query, documents[0].content)
        support = self._calculate_support(query, documents)

        confidence = (
            self.weights["retrieval"] * top_score
            + self.weights["gap"] * score_gap
            + self.weights["coverage"] * top_coverage
            + self.weights["support"] * support
        )
        return round(self._clamp(confidence), 2)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    def _query_terms(self, query: str) -> set[str]:
        tokens = {token.strip().lower() for token in jieba.cut(query) if token and token.strip()}
        return {token for token in tokens if len(token) >= 2 and token not in self.stopwords}

    def _calculate_coverage(self, query: str, document: str) -> float:
        query_terms = self._query_terms(query)
        if not query_terms:
            return 0.0

        doc_terms = {token.strip().lower() for token in jieba.cut(document) if token and token.strip()}
        hit_count = len(query_terms & doc_terms)
        return hit_count / len(query_terms)

    def _calculate_support(self, query: str, documents: Iterable[Document]) -> float:
        query_terms = self._query_terms(query)
        if not query_terms:
            return 0.0

        covered = set()
        distinct_sources = set()
        total = 0
        for document in documents:
            total += 1
            distinct_sources.add(document.source)
            doc_terms = {token.strip().lower() for token in jieba.cut(document.content) if token and token.strip()}
            covered.update(query_terms & doc_terms)

        source_bonus = min(len(distinct_sources) / 2, 1.0) * 0.2
        doc_bonus = min(total / 3, 1.0) * 0.2
        term_support = len(covered) / len(query_terms)
        return self._clamp(term_support * 0.6 + source_bonus + doc_bonus)

    def get_confidence_level(self, confidence: float) -> str:
        if confidence >= 0.8:
            return "高"
        if confidence >= 0.6:
            return "中"
        if confidence >= 0.4:
            return "低"
        return "极低"

    def should_answer(self, confidence: float, threshold: float = 0.4) -> bool:
        return confidence >= threshold
