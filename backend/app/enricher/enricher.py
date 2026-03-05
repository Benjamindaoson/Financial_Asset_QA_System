"""
Query Enricher - Rule-based hint injection (zero-cost)
"""
from typing import List


class QueryEnricher:
    """
    Injects contextual hints into queries based on keyword detection
    No LLM call - pure rule-based system
    """

    # Keyword patterns for different query types
    MARKET_KEYWORDS = [
        "价格", "股价", "行情", "涨", "跌", "市值", "PE", "市盈率",
        "历史", "走势", "K线", "成交量", "最高", "最低"
    ]

    KNOWLEDGE_KEYWORDS = [
        "什么是", "如何", "怎么", "定义", "解释", "含义", "计算",
        "公式", "指标", "概念", "原理"
    ]

    NEWS_KEYWORDS = [
        "为什么", "原因", "新闻", "事件", "公告", "财报", "消息",
        "影响", "分析", "最近", "今天", "昨天"
    ]

    @classmethod
    def enrich(cls, query: str) -> str:
        """
        Add contextual hints based on query type detection
        Returns: enriched query with hints prepended
        """
        hints = []

        # Detect query type
        if any(kw in query for kw in cls.MARKET_KEYWORDS):
            hints.append("[Hint: 涉及行情数据，优先使用 get_price/get_history/get_change 工具]")

        if any(kw in query for kw in cls.KNOWLEDGE_KEYWORDS):
            hints.append("[Hint: 涉及金融知识，优先使用 search_knowledge 工具]")

        if any(kw in query for kw in cls.NEWS_KEYWORDS):
            hints.append("[Hint: 涉及新闻事件，考虑使用 search_web 工具]")

        # If no specific hints, add general guidance
        if not hints:
            hints.append("[Hint: 分析问题类型，选择合适的工具获取事实数据]")

        # Prepend hints to query
        enriched = "\n".join(hints) + "\n\n" + query
        return enriched

    @classmethod
    def extract_symbols(cls, query: str) -> List[str]:
        """
        Extract potential stock symbols from query
        Simple heuristic: look for uppercase words or known patterns
        """
        symbols = []
        words = query.split()

        for word in words:
            # Check for ticker-like patterns
            if word.isupper() and 2 <= len(word) <= 5:
                symbols.append(word)
            # Check for A-share patterns (6 digits)
            elif word.isdigit() and len(word) == 6:
                symbols.append(word)

        return symbols
