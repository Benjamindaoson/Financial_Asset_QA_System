"""Deterministic query router for financial QA."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from app.enricher.enricher import QueryEnricher
from app.market.service import TickerMapper


class QueryType(str, Enum):
    MARKET = "market"
    KNOWLEDGE = "knowledge"
    NEWS = "news"
    HYBRID = "hybrid"


@dataclass
class QueryRoute:
    query_type: QueryType
    cleaned_query: str
    symbols: List[str] = field(default_factory=list)
    days: Optional[int] = None
    requires_price: bool = False
    requires_history: bool = False
    requires_change: bool = False
    requires_info: bool = False
    requires_knowledge: bool = False
    requires_web: bool = False


class QueryRouter:
    """Rule-based router that forces deterministic execution paths."""

    MARKET_KEYWORDS = {
        "价格",
        "股价",
        "行情",
        "走势",
        "涨跌",
        "涨幅",
        "跌幅",
        "市值",
        "quote",
        "price",
        "k线",
        "历史",
        "chart",
        "trend",
        "volume",
    }
    KNOWLEDGE_KEYWORDS = {
        "什么是",
        "定义",
        "含义",
        "解释",
        "如何",
        "计算",
        "公式",
        "概念",
        "区别",
        "what is",
        "definition",
        "meaning",
        "difference",
    }
    NEWS_KEYWORDS = {
        "为什么",
        "原因",
        "新闻",
        "事件",
        "公告",
        "财报",
        "消息",
        "影响",
        "最近",
        "最新",
        "today",
        "yesterday",
        "news",
        "event",
        "reason",
        "earnings",
    }
    CURRENT_PRICE_KEYWORDS = {"当前", "现在", "实时", "最新价", "现价", "today", "now"}
    CHANGE_KEYWORDS = {"涨跌", "涨幅", "跌幅", "表现", "走势", "trend", "performance"}
    HISTORY_KEYWORDS = {"历史", "k线", "chart", "走势", "trend"}
    INFO_KEYWORDS = {"市值", "市盈率", "pe", "行业", "sector", "industry", "基本面", "信息"}
    REPORT_KEYWORDS = {"季度", "财报", "业绩", "earnings", "10-k", "10-q", "quarter"}

    async def classify_async(self, query: str) -> QueryRoute:
        return self.classify(query)

    def classify(self, query: str) -> QueryRoute:
        cleaned = self._clean_query(query)
        lowered = cleaned.lower()
        symbols = self._extract_symbols(cleaned)
        days = self._extract_days(cleaned)

        has_market = self._contains_any(cleaned, lowered, self.MARKET_KEYWORDS) or bool(symbols)
        has_knowledge = self._contains_any(cleaned, lowered, self.KNOWLEDGE_KEYWORDS)
        has_news = self._contains_any(cleaned, lowered, self.NEWS_KEYWORDS)
        has_report = self._contains_any(cleaned, lowered, self.REPORT_KEYWORDS)

        if has_market and (has_news or has_report):
            route_type = QueryType.HYBRID
        elif has_market:
            route_type = QueryType.MARKET
        elif has_news or has_report:
            route_type = QueryType.NEWS
        else:
            route_type = QueryType.KNOWLEDGE

        route = QueryRoute(query_type=route_type, cleaned_query=cleaned, symbols=symbols, days=days)

        if route_type == QueryType.MARKET:
            route.requires_price = self._contains_any(cleaned, lowered, self.CURRENT_PRICE_KEYWORDS) or not self._contains_any(
                cleaned,
                lowered,
                self.CHANGE_KEYWORDS | self.HISTORY_KEYWORDS | self.INFO_KEYWORDS,
            )
            route.requires_change = self._contains_any(cleaned, lowered, self.CHANGE_KEYWORDS)
            route.requires_history = self._contains_any(cleaned, lowered, self.HISTORY_KEYWORDS)
            route.requires_info = self._contains_any(cleaned, lowered, self.INFO_KEYWORDS) and not route.requires_price
            if not any([route.requires_price, route.requires_change, route.requires_history, route.requires_info]):
                route.requires_price = True
        elif route_type == QueryType.KNOWLEDGE:
            route.requires_knowledge = has_knowledge or bool(cleaned.strip())
            if has_report:
                route.requires_web = True
                route.query_type = QueryType.HYBRID
        elif route_type == QueryType.NEWS:
            route.requires_web = True
        elif route_type == QueryType.HYBRID:
            route.requires_change = bool(symbols)
            route.requires_price = self._contains_any(cleaned, lowered, self.CURRENT_PRICE_KEYWORDS)
            route.requires_history = self._contains_any(cleaned, lowered, self.HISTORY_KEYWORDS)
            route.requires_web = True
            route.requires_knowledge = has_report or has_knowledge

        return route

    def _clean_query(self, query: str) -> str:
        lines = [line for line in query.splitlines() if not line.strip().startswith("[Hint:")]
        return "\n".join(lines).strip()

    def _extract_symbols(self, query: str) -> List[str]:
        symbols = QueryEnricher.extract_symbols(query)
        if symbols:
            return [TickerMapper.normalize(symbol) for symbol in symbols]

        inline_symbols = re.findall(r"(?<![A-Za-z])([A-Z]{2,5}(?:\.[A-Z]{1,3})?)(?![A-Za-z])", query)
        if inline_symbols:
            return [TickerMapper.normalize(symbol) for symbol in inline_symbols]

        for alias, symbol in TickerMapper.EXACT_MAP.items():
            if alias in query:
                return [symbol]

        return []

    def _extract_days(self, query: str) -> Optional[int]:
        day_match = re.search(r"(\d+)\s*天", query)
        if day_match:
            return int(day_match.group(1))

        month_match = re.search(r"(\d+)\s*(月|个月)", query)
        if month_match:
            return int(month_match.group(1)) * 30

        week_match = re.search(r"(\d+)\s*周", query)
        if week_match:
            return int(week_match.group(1)) * 7

        return None

    @staticmethod
    def _contains_any(original: str, lowered: str, keywords: set[str]) -> bool:
        return any(keyword in original or keyword in lowered for keyword in keywords)
