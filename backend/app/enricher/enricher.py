"""Query enricher and ticker extraction helpers."""

from __future__ import annotations

import re
from typing import List


class QueryEnricher:
    """Inject lightweight routing hints without mutating the user query."""

    MARKET_KEYWORDS = ["价格", "股价", "行情", "涨", "跌", "市值", "PE", "市盈率", "历史", "走势", "K线", "成交量", "最高", "最低"]
    KNOWLEDGE_KEYWORDS = ["什么是", "如何", "怎么", "定义", "解释", "含义", "计算", "公式", "指标", "概念", "原理"]
    NEWS_KEYWORDS = ["为什么", "原因", "新闻", "事件", "公告", "财报", "消息", "影响", "分析", "最近", "今天", "昨天"]

    @classmethod
    def enrich(cls, query: str) -> str:
        hints: List[str] = []
        if any(keyword.lower() in query.lower() or keyword in query for keyword in cls.MARKET_KEYWORDS):
            hints.append("[Hint: Use market data tools when facts depend on live prices or history.]")
        if any(keyword.lower() in query.lower() or keyword in query for keyword in cls.KNOWLEDGE_KEYWORDS):
            hints.append("[Hint: Use knowledge retrieval before answering concept questions.]")
        if any(keyword.lower() in query.lower() or keyword in query for keyword in cls.NEWS_KEYWORDS):
            hints.append("[Hint: Use news or filings retrieval when the query asks for causes or recent events.]")
        if not hints:
            hints.append("[Hint: Classify the query and gather facts before answering.]")
        return "\n".join(hints) + "\n\n" + query

    @classmethod
    def extract_symbols(cls, query: str) -> List[str]:
        symbols = []
        for token in re.findall(r"\b[A-Z]{2,5}(?:\.[A-Z]{1,3})?\b", query):
            symbols.append(token)
        for token in re.findall(r"\b\d{6}\b", query):
            symbols.append(token)
        return list(dict.fromkeys(symbols))
