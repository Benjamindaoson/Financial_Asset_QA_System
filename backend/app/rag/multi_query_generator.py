"""
多查询生成器 - 从单个查询生成多个视角的查询变体
Multi-Query Generator - Generate multiple query perspectives from a single query
"""
from typing import List
import re


class MultiQueryGenerator:
    """多查询生成器"""

    # 金融术语同义词映射
    TERM_SYNONYMS = {
        "PE": ["市盈率", "price-to-earnings", "盈利倍数"],
        "PB": ["市净率", "price-to-book", "账面价值比"],
        "ROE": ["净资产收益率", "return on equity", "股东回报率"],
        "市盈率": ["PE", "盈利倍数", "估值倍数"],
        "市净率": ["PB", "账面价值比"],
        "波动率": ["volatility", "风险", "价格波动"],
        "回撤": ["drawdown", "最大回撤", "亏损幅度"],
    }

    # 查询模板
    QUERY_TEMPLATES = {
        "definition": [
            "{term}的定义是什么？",
            "解释一下{term}",
            "{term}是什么意思？",
        ],
        "comparison": [
            "对比{entity1}和{entity2}的{metric}",
            "{entity1}与{entity2}的{metric}有什么区别？",
            "{entity1}和{entity2}在{metric}方面的表现",
        ],
        "data": [
            "{entity}的{metric}是多少？",
            "查询{entity}的{metric}数据",
            "{entity}{metric}的具体数值",
        ],
    }

    def __init__(self):
        pass

    def generate_queries(self, query: str, num_queries: int = 3) -> List[str]:
        """
        生成多个查询变体

        Args:
            query: 原始查询
            num_queries: 生成查询数量

        Returns:
            查询列表（包含原查询）
        """
        queries = [query]  # 始终包含原查询

        # 1. 同义词替换
        synonym_queries = self._generate_synonym_variants(query)
        queries.extend(synonym_queries[:num_queries-1])

        # 2. 如果是对比查询，分解为单独查询
        if self._is_comparison_query(query):
            decomposed = self._decompose_comparison(query)
            queries.extend(decomposed)

        # 3. 去重并限制数量
        unique_queries = []
        seen = set()
        for q in queries:
            if q not in seen:
                unique_queries.append(q)
                seen.add(q)
                if len(unique_queries) >= num_queries:
                    break

        return unique_queries

    def _generate_synonym_variants(self, query: str) -> List[str]:
        """生成同义词变体"""
        variants = []

        for term, synonyms in self.TERM_SYNONYMS.items():
            if term in query:
                for synonym in synonyms[:2]:  # 最多2个同义词
                    variant = query.replace(term, synonym)
                    if variant != query:
                        variants.append(variant)

        return variants

    def _is_comparison_query(self, query: str) -> bool:
        """判断是否为对比查询"""
        comparison_keywords = ["对比", "比较", "vs", "versus", "和", "与"]
        return any(kw in query for kw in comparison_keywords)

    def _decompose_comparison(self, query: str) -> List[str]:
        """分解对比查询为单独查询"""
        decomposed = []

        # 提取实体（简单实现）
        # 例如: "对比苹果和微软的市盈率" -> ["苹果的市盈率", "微软的市盈率"]

        # 匹配 "A和B的X" 模式
        pattern = r"(.+?)[和与](.+?)的(.+)"
        match = re.search(pattern, query)

        if match:
            entity1 = match.group(1).replace("对比", "").replace("比较", "").strip()
            entity2 = match.group(2).strip()
            metric = match.group(3).strip()

            decomposed.append(f"{entity1}的{metric}")
            decomposed.append(f"{entity2}的{metric}")

        return decomposed
