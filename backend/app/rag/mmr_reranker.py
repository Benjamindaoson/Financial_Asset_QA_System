"""
MMR重排序器 - 使用Maximal Marginal Relevance提升结果多样性
MMR Reranker - Use Maximal Marginal Relevance for diverse results
"""
from typing import List, Callable
from app.models.schemas import Document


class MMRReranker:
    """MMR (Maximal Marginal Relevance) 重排序器"""

    def __init__(self, lambda_param: float = 0.7):
        """
        初始化

        Args:
            lambda_param: 相关性与多样性的权衡参数 (0-1)
                         1.0 = 完全基于相关性
                         0.0 = 完全基于多样性
        """
        self.lambda_param = lambda_param

    def rerank(
        self,
        documents: List[Document],
        top_n: int,
        similarity_fn: Callable[[Document, Document], float]
    ) -> List[Document]:
        """
        使用MMR重排序文档

        Args:
            documents: 候选文档列表（已按相关性排序）
            top_n: 返回文档数量
            similarity_fn: 文档相似度计算函数

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        if len(documents) <= top_n:
            return documents

        # 初始化
        selected = []
        remaining = documents.copy()

        # 第一个文档：选择最相关的
        selected.append(remaining.pop(0))

        # 迭代选择剩余文档
        while len(selected) < top_n and remaining:
            best_score = float('-inf')
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                # 计算相关性分数（使用原始score）
                relevance = candidate.score

                # 计算与已选文档的最大相似度
                max_similarity = max(
                    similarity_fn(candidate, selected_doc)
                    for selected_doc in selected
                )

                # MMR分数 = λ * 相关性 - (1-λ) * 最大相似度
                mmr_score = (
                    self.lambda_param * relevance -
                    (1 - self.lambda_param) * max_similarity
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            # 选择最佳候选
            selected.append(remaining.pop(best_idx))

        return selected

    @staticmethod
    def cosine_similarity(doc1: Document, doc2: Document) -> float:
        """
        计算两个文档的余弦相似度（基于内容）

        简化实现：基于字符集合的Jaccard相似度

        Args:
            doc1: 文档1
            doc2: 文档2

        Returns:
            相似度分数 (0-1)
        """
        # 简化实现：使用字符级Jaccard相似度
        set1 = set(doc1.content)
        set2 = set(doc2.content)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union
