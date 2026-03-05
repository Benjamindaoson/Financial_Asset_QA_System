"""
置信度评分器 - 量化答案可信度
Confidence Scorer for answer reliability
"""
from typing import List
import jieba
from app.models import Document


class ConfidenceScorer:
    """
    置信度评分器

    评分维度：
    1. 检索分数 (40%) - 重排序后的相似度
    2. 分数差距 (30%) - Top-1 vs Top-2 的差距
    3. 覆盖度 (30%) - 查询词在文档中的覆盖率
    """

    def __init__(self):
        self.weights = {
            'retrieval': 0.4,
            'gap': 0.3,
            'coverage': 0.3
        }

    def calculate(
        self,
        query: str,
        documents: List[Document]
    ) -> float:
        """
        计算置信度分数

        Args:
            query: 查询文本
            documents: 检索到的文档列表

        Returns:
            置信度分数 (0-1)
        """
        if not documents:
            return 0.0

        # 1. 检索分数 (重排序后的相似度)
        retrieval_score = documents[0].score

        # 2. 分数差距 (Top-1 vs Top-2)
        score_gap = 0.0
        if len(documents) >= 2:
            gap = documents[0].score - documents[1].score
            # 归一化到0-1，差距越大置信度越高
            score_gap = min(gap * 2, 1.0)

        # 3. 覆盖度 (查询词在文档中的比例)
        coverage = self._calculate_coverage(query, documents[0].content)

        # 4. 综合置信度
        confidence = (
            self.weights['retrieval'] * retrieval_score +
            self.weights['gap'] * score_gap +
            self.weights['coverage'] * coverage
        )

        return round(confidence, 2)

    def _calculate_coverage(self, query: str, document: str) -> float:
        """
        计算查询词覆盖度

        Args:
            query: 查询文本
            document: 文档文本

        Returns:
            覆盖度 (0-1)
        """
        # 分词
        query_tokens = set(jieba.cut(query))
        doc_tokens = set(jieba.cut(document))

        # 移除停用词（简单版本）
        stopwords = {'的', '了', '是', '在', '有', '和', '与', '或', '等', '吗', '呢', '啊'}
        query_tokens = query_tokens - stopwords

        if not query_tokens:
            return 0.0

        # 计算交集
        intersection = query_tokens & doc_tokens

        # 覆盖率
        coverage = len(intersection) / len(query_tokens)

        return coverage

    def get_confidence_level(self, confidence: float) -> str:
        """
        获取置信度等级

        Args:
            confidence: 置信度分数

        Returns:
            置信度等级描述
        """
        if confidence >= 0.8:
            return "高"
        elif confidence >= 0.6:
            return "中"
        elif confidence >= 0.4:
            return "低"
        else:
            return "极低"

    def should_answer(self, confidence: float, threshold: float = 0.4) -> bool:
        """
        判断是否应该回答

        Args:
            confidence: 置信度分数
            threshold: 置信度阈值

        Returns:
            是否应该回答
        """
        return confidence >= threshold
