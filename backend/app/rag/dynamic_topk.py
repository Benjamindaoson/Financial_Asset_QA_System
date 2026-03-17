"""
动态Top-K计算器 - 根据查询复杂度动态调整检索数量
Dynamic Top-K Calculator - Adjust retrieval count based on query complexity
"""
import re
from typing import List


class DynamicTopKCalculator:
    """动态Top-K计算器"""

    # 复杂度指标关键词
    COMPARISON_KEYWORDS = {"对比", "比较", "vs", "versus", "哪个", "区别"}
    MULTI_METRIC_KEYWORDS = {"和", "与", "以及", "还有"}
    COMPLEX_KEYWORDS = {"分析", "评估", "综合", "全面", "详细"}

    def __init__(self, base_k: int = 5, max_k: int = 15):
        """
        初始化

        Args:
            base_k: 基础K值
            max_k: 最大K值
        """
        self.base_k = base_k
        self.max_k = max_k

    def calculate_topk(self, query: str) -> int:
        """
        计算动态Top-K值

        Args:
            query: 查询文本

        Returns:
            Top-K值
        """
        complexity_score = 0

        # 1. 检测对比查询 (+2)
        if any(kw in query for kw in self.COMPARISON_KEYWORDS):
            complexity_score += 2

        # 2. 检测多指标查询 (+1 per metric)
        metric_count = sum(1 for kw in self.MULTI_METRIC_KEYWORDS if kw in query)
        complexity_score += metric_count

        # 3. 检测复杂分析需求 (+2)
        if any(kw in query for kw in self.COMPLEX_KEYWORDS):
            complexity_score += 2

        # 4. 检测实体数量 (+1 per entity beyond first)
        entity_count = self._count_entities(query)
        if entity_count > 1:
            complexity_score += (entity_count - 1)

        # 5. 查询长度 (+1 if > 30 chars)
        if len(query) > 30:
            complexity_score += 1

        # 计算最终K值
        k = self.base_k + complexity_score
        k = min(k, self.max_k)  # 不超过最大值

        return k

    def _count_entities(self, query: str) -> int:
        """
        估算查询中的实体数量

        Args:
            query: 查询文本

        Returns:
            实体数量估计
        """
        # 简单实现：检测股票代码和公司名称
        # 股票代码模式: AAPL, MSFT, 600519等
        ticker_pattern = r'\b[A-Z]{2,5}\b|\b\d{6}\b'
        tickers = re.findall(ticker_pattern, query)

        # 常见公司名称
        company_names = ["苹果", "微软", "谷歌", "特斯拉", "亚马逊", "阿里", "腾讯", "茅台"]
        companies = [name for name in company_names if name in query]

        # 检测顿号、逗号分隔的列表
        if "、" in query or "，" in query:
            parts = re.split(r"[、，]", query)
            # 过滤掉短片段
            entities = [p.strip() for p in parts if len(p.strip()) >= 2]
            return max(len(entities), len(tickers) + len(companies))

        return len(tickers) + len(companies)
