"""
Iterative retrieval: sufficiency check and optional second retrieval round.
"""
from __future__ import annotations

from typing import List

from app.config import settings
from app.models import Document


class IterativeRetriever:
    """Check if retrieval is sufficient and optionally rewrite for second round."""

    def sufficiency_check(
        self,
        query: str,
        documents: List[Document],
    ) -> bool:
        """
        Check if the retrieved documents are sufficient to answer the query.

        Uses rule-based heuristics: min docs and min score threshold.

        Args:
            query: User query
            documents: Retrieved documents

        Returns:
            True if sufficient, False if second round should be attempted
        """
        if not documents:
            return False
        min_docs = settings.ITERATIVE_RETRIEVAL_SUFFICIENCY_MIN_DOCS
        min_score = settings.ITERATIVE_RETRIEVAL_SUFFICIENCY_MIN_SCORE
        if len(documents) < min_docs:
            return False
        top_score = max(doc.score for doc in documents) if documents else 0.0
        return top_score >= min_score

    def rewrite_for_retrieval(
        self,
        query: str,
        documents: List[Document],
    ) -> str:
        """
        Rewrite the query for a second retrieval round, incorporating context from first round.

        Args:
            query: Original query
            documents: Documents from first round

        Returns:
            Rewritten query string
        """
        if not documents:
            return query
        snippet = documents[0].content[:200].strip() if documents else ""
        return f"根据以下内容，补充检索：{query}\n\n已有片段：{snippet}..."
