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
        "\u4ef7\u683c",
        "\u80a1\u4ef7",
        "\u884c\u60c5",
        "\u8d70\u52bf",
        "\u6da8\u8dcc",
        "\u6da8\u5e45",
        "\u8dcc\u5e45",
        "\u5e02\u503c",
        "quote",
        "price",
        "k\u7ebf",
        "\u5386\u53f2",
        "chart",
        "trend",
        "volume",
    }
    KNOWLEDGE_KEYWORDS = {
        "\u4ec0\u4e48\u662f",
        "\u5b9a\u4e49",
        "\u542b\u4e49",
        "\u89e3\u91ca",
        "\u5982\u4f55",
        "\u8ba1\u7b97",
        "\u516c\u5f0f",
        "\u6982\u5ff5",
        "\u533a\u522b",
        "what is",
        "definition",
        "meaning",
        "difference",
    }
    NEWS_KEYWORDS = {
        "\u4e3a\u4ec0\u4e48",
        "\u539f\u56e0",
        "\u65b0\u95fb",
        "\u4e8b\u4ef6",
        "\u516c\u544a",
        "\u8d22\u62a5",
        "\u6d88\u606f",
        "\u5f71\u54cd",
        "\u6700\u8fd1",
        "\u6700\u65b0",
        "today",
        "yesterday",
        "news",
        "event",
        "reason",
        "earnings",
    }
    CURRENT_PRICE_KEYWORDS = {
        "\u5f53\u524d",
        "\u73b0\u5728",
        "\u5b9e\u65f6",
        "\u6700\u65b0\u4ef7",
        "\u73b0\u4ef7",
        "today",
        "now",
    }
    CHANGE_KEYWORDS = {
        "\u6da8\u8dcc",
        "\u6da8\u5e45",
        "\u8dcc\u5e45",
        "\u8868\u73b0",
        "\u8d70\u52bf",
        "trend",
        "performance",
    }
    HISTORY_KEYWORDS = {
        "\u5386\u53f2",
        "k\u7ebf",
        "chart",
        "\u8d70\u52bf",
        "trend",
    }
    INFO_KEYWORDS = {
        "\u5e02\u503c",
        "\u5e02\u76c8\u7387",
        "pe",
        "\u884c\u4e1a",
        "sector",
        "industry",
        "\u57fa\u672c\u9762",
        "\u4fe1\u606f",
    }
    REPORT_KEYWORDS = {
        "\u5b63\u5ea6",
        "\u8d22\u62a5",
        "\u4e1a\u7ee9",
        "earnings",
        "10-k",
        "10-q",
        "quarter",
    }

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

        route = QueryRoute(
            query_type=route_type,
            cleaned_query=cleaned,
            symbols=symbols,
            days=days,
        )

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
        day_match = re.search(r"(\d+)\s*\u5929", query)
        if day_match:
            return int(day_match.group(1))

        month_match = re.search(r"(\d+)\s*(\u6708|\u4e2a\u6708)", query)
        if month_match:
            return int(month_match.group(1)) * 30

        week_match = re.search(r"(\d+)\s*\u5468", query)
        if week_match:
            return int(week_match.group(1)) * 7

        return None

    @staticmethod
    def _contains_any(original: str, lowered: str, keywords: set[str]) -> bool:
        return any(keyword in original or keyword in lowered for keyword in keywords)
