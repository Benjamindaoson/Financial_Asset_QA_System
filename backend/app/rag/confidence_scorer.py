"""
置信度评分器 - 多维度评估答案质量
Confidence Scorer - Multi-dimensional answer quality assessment
"""
import re
from typing import List, Dict
from app.models.schemas import Document


class ConfidenceScorer:
    """置信度评分器"""

    def __init__(
        self,
        retrieval_weight: float = 0.4,
        answer_weight: float = 0.3,
        citation_weight: float = 0.3
    ):
        """
        初始化

        Args:
            retrieval_weight: 检索质量权重
            answer_weight: 答案质量权重
            citation_weight: 引用质量权重
        """
        self.retrieval_weight = retrieval_weight
        self.answer_weight = answer_weight
        self.citation_weight = citation_weight

    def calculate_confidence(
        self,
        answer: str,
        documents: List[Document],
        query: str
    ) -> float:
        """
        计算整体置信度

        Args:
            answer: 生成的答案
            documents: 检索到的文档
            query: 原始查询

        Returns:
            置信度分数 (0-1)
        """
        breakdown = self.calculate_confidence_breakdown(answer, documents, query)
        return breakdown["overall"]

    def calculate_confidence_breakdown(
        self,
        answer: str,
        documents: List[Document],
        query: str
    ) -> Dict[str, float]:
        """
        计算置信度分解

        Args:
            answer: 生成的答案
            documents: 检索到的文档
            query: 原始查询

        Returns:
            置信度分解字典
        """
        # 1. 检索质量评分
        retrieval_score = self._score_retrieval_quality(documents)

        # 2. 答案质量评分
        answer_score = self._score_answer_quality(answer, query)

        # 3. 引用质量评分
        citation_score = self._score_citation_quality(answer, documents)

        # 4. 计算加权总分
        overall = (
            self.retrieval_weight * retrieval_score +
            self.answer_weight * answer_score +
            self.citation_weight * citation_score
        )

        return {
            "overall": overall,
            "retrieval_quality": retrieval_score,
            "answer_quality": answer_score,
            "citation_quality": citation_score,
        }

    def _score_retrieval_quality(self, documents: List[Document]) -> float:
        """评估检索质量"""
        if not documents:
            return 0.0

        num_docs = len(documents)
        if num_docs <= 3:
            doc_count_score = 1.0
        elif num_docs <= 5:
            doc_count_score = 0.8
        else:
            doc_count_score = 0.6

        avg_score = sum(doc.score for doc in documents) / len(documents)
        top_score = documents[0].score if documents else 0.0

        retrieval_quality = (
            0.3 * doc_count_score +
            0.4 * avg_score +
            0.3 * top_score
        )

        return min(retrieval_quality, 1.0)

    def _score_answer_quality(self, answer: str, query: str) -> float:
        """评估答案质量"""
        if not answer:
            return 0.0

        refusal_keywords = ["无法回答", "没有相关", "不清楚", "不确定"]
        if any(kw in answer for kw in refusal_keywords):
            return 0.3

        answer_len = len(answer)
        if answer_len < 20:
            length_score = 0.5
        elif answer_len <= 200:
            length_score = 1.0
        elif answer_len <= 500:
            length_score = 0.8
        else:
            length_score = 0.6

        query_terms = set(query.replace("？", "").replace("?", "").split())
        answer_terms = set(answer.split())
        if query_terms:
            keyword_coverage = len(query_terms & answer_terms) / len(query_terms)
        else:
            keyword_coverage = 0.5

        answer_quality = 0.6 * length_score + 0.4 * keyword_coverage
        return min(answer_quality, 1.0)

    def _score_citation_quality(self, answer: str, documents: List[Document]) -> float:
        """评估引用质量"""
        citation_pattern = re.compile(r'\[文档(\d+)\]')
        citations = citation_pattern.findall(answer)

        if not citations:
            return 0.0

        num_citations = len(citations)
        citation_nums = [int(c) for c in citations]
        num_docs = len(documents)
        valid_citations = [c for c in citation_nums if 1 <= c <= num_docs]

        if not valid_citations:
            return 0.2

        validity_ratio = len(valid_citations) / len(citation_nums)

        if num_citations <= 3:
            count_score = 1.0
        elif num_citations <= 5:
            count_score = 0.8
        else:
            count_score = 0.6

        citation_quality = 0.7 * validity_ratio + 0.3 * count_score
        return min(citation_quality, 1.0)
