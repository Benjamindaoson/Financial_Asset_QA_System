"""Deterministic query router for the production financial QA flow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

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
    range_key: Optional[str] = None
    requires_price: bool = False
    requires_history: bool = False
    requires_change: bool = False
    requires_info: bool = False
    requires_metrics: bool = False
    requires_comparison: bool = False
    requires_knowledge: bool = False
    requires_web: bool = False
    requires_sec: bool = False
    refuses_advice: bool = False


class QueryRouter:
    """Rule-based router that produces deterministic execution plans."""

    MARKET_KEYWORDS: Set[str] = {
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
        "chart",
        "trend",
        "volume",
        "etf",
        "bond",
    }
    KNOWLEDGE_KEYWORDS: Set[str] = {
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
        "explain",
    }
    NEWS_KEYWORDS: Set[str] = {
        "为什么",
        "原因",
        "新闻",
        "事件",
        "公告",
        "财报",
        "消息",
        "影响",
        "最新",
        "最近",
        "news",
        "event",
        "why",
        "reason",
        "latest",
        "recent",
        "earnings",
    }
    CURRENT_PRICE_KEYWORDS: Set[str] = {
        "当前",
        "现在",
        "实时",
        "最新价",
        "现价",
        "today",
        "now",
        "current",
        "latest price",
    }
    CHANGE_KEYWORDS: Set[str] = {
        "涨跌",
        "涨幅",
        "跌幅",
        "表现",
        "走势",
        "回报",
        "收益率",
        "trend",
        "performance",
        "return",
        "down",
        "up",
    }
    HISTORY_KEYWORDS: Set[str] = {
        "历史",
        "走势图",
        "图表",
        "k线",
        "chart",
        "history",
        "trend",
        "ytd",
        "1y",
        "3m",
        "6m",
        "5y",
        "year to date",
    }
    INFO_KEYWORDS: Set[str] = {
        "市值",
        "市盈率",
        "行业",
        "板块",
        "公司信息",
        "基本面",
        "信息",
        "profile",
        "company profile",
        "sector",
        "industry",
    }
    METRIC_KEYWORDS: Set[str] = {
        "波动率",
        "收益率",
        "最大回撤",
        "回撤",
        "volatility",
        "return",
        "drawdown",
        "sharpe",
        "risk",
        "beta",
    }
    REPORT_KEYWORDS: Set[str] = {
        "财报",
        "业绩",
        "公告",
        "10-k",
        "10-q",
        "8-k",
        "filing",
        "sec",
        "edgar",
        "earnings",
        "annual report",
        "quarterly report",
    }
    COMPARE_KEYWORDS: Set[str] = {
        "对比",
        "比较",
        "哪个更好",
        "vs",
        "versus",
        "compare",
    }
    ADVICE_KEYWORDS: Set[str] = {
        "可以买",
        "值得买吗",
        "该买",
        "买入",
        "卖出",
        "推荐",
        "投资建议",
        "目标价",
        "会涨吗",
        "会跌吗",
        "should i buy",
        "buy or sell",
        "target price",
        "recommend",
        "will it rise",
        "will it fall",
    }
    RANGE_MAP = {
        "ytd": "ytd",
        "year to date": "ytd",
        "年初至今": "ytd",
        "今年以来": "ytd",
        "1年": "1y",
        "一年": "1y",
        "1y": "1y",
        "12m": "1y",
        "5年": "5y",
        "五年": "5y",
        "5y": "5y",
        "3个月": "3m",
        "三个月": "3m",
        "3m": "3m",
        "6个月": "6m",
        "六个月": "6m",
        "6m": "6m",
        "1个月": "1m",
        "一个月": "1m",
        "1m": "1m",
    }
    NON_TICKER_UPPERCASE = {"PE", "PB", "PS", "ROE", "ROA", "EPS", "RSI", "MACD"}
    VALUATION_PATTERNS = {
        "price-to-earnings",
        "price to earnings",
        "price-to-book",
        "price to book",
        "price-to-sales",
        "price to sales",
        "p/e",
        "p/b",
        "p/s",
        "pe ratio",
        "pb ratio",
        "ps ratio",
    }
    REPORT_SUPPRESSION_PATTERNS = VALUATION_PATTERNS

    async def classify_async(self, query: str) -> QueryRoute:
        return self.classify(query)

    def classify(self, query: str) -> QueryRoute:
        cleaned = self._clean_query(query)
        lowered = cleaned.lower()
        symbols = self._extract_symbols(cleaned)
        days = self._extract_days(cleaned, lowered)
        range_key = self._extract_range(cleaned, lowered)

        has_knowledge = self._contains_any(cleaned, lowered, self.KNOWLEDGE_KEYWORDS)
        has_market = self._contains_market_intent(cleaned, lowered, symbols, has_knowledge)
        has_news = self._contains_news_intent(cleaned, lowered)
        has_report = self._contains_report_intent(cleaned, lowered)

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
            range_key=range_key,
        )

        route.requires_comparison = len(symbols) >= 2 or self._contains_any(cleaned, lowered, self.COMPARE_KEYWORDS)
        route.requires_metrics = self._contains_any(cleaned, lowered, self.METRIC_KEYWORDS)
        route.refuses_advice = self._contains_any(cleaned, lowered, self.ADVICE_KEYWORDS)

        if route_type == QueryType.MARKET:
            route.requires_price = self._requires_market_price(cleaned, lowered)
            route.requires_change = self._contains_any(cleaned, lowered, self.CHANGE_KEYWORDS)
            route.requires_history = self._contains_any(cleaned, lowered, self.HISTORY_KEYWORDS) or route.requires_metrics
            route.requires_info = self._contains_any(cleaned, lowered, self.INFO_KEYWORDS)
        elif route_type == QueryType.KNOWLEDGE:
            route.requires_knowledge = True
        elif route_type == QueryType.NEWS:
            route.requires_web = True
            route.requires_sec = has_report
        elif route_type == QueryType.HYBRID:
            route.requires_price = bool(symbols)
            route.requires_change = bool(symbols)
            route.requires_history = self._contains_any(cleaned, lowered, self.HISTORY_KEYWORDS) or route.requires_metrics
            route.requires_info = self._contains_any(cleaned, lowered, self.INFO_KEYWORDS)
            route.requires_web = True
            route.requires_sec = has_report
            route.requires_knowledge = has_knowledge or has_report

        if route.requires_comparison:
            route.requires_history = True
            route.requires_metrics = True
            route.requires_price = True

        if route.requires_metrics:
            route.requires_history = True

        if route.requires_change and days is not None:
            route.requires_history = True

        return route

    def _requires_market_price(self, original: str, lowered: str) -> bool:
        if self._contains_any(original, lowered, self.CURRENT_PRICE_KEYWORDS):
            return True
        specific_market_intent = (
            self._contains_any(original, lowered, self.CHANGE_KEYWORDS)
            or self._contains_any(original, lowered, self.HISTORY_KEYWORDS)
            or self._contains_any(original, lowered, self.INFO_KEYWORDS)
            or self._contains_any(original, lowered, self.METRIC_KEYWORDS)
        )
        return not specific_market_intent

    def _contains_market_intent(
        self,
        original: str,
        lowered: str,
        symbols: List[str],
        has_knowledge: bool,
    ) -> bool:
        if symbols:
            return True

        if any(pattern in lowered for pattern in self.VALUATION_PATTERNS) and has_knowledge:
            return False

        return self._contains_any(original, lowered, self.MARKET_KEYWORDS)

    def _contains_news_intent(self, original: str, lowered: str) -> bool:
        keywords = self.NEWS_KEYWORDS
        if "earnings" in lowered and any(pattern in lowered for pattern in self.REPORT_SUPPRESSION_PATTERNS):
            keywords = keywords - {"earnings"}
        return self._contains_any(original, lowered, keywords)

    def _contains_report_intent(self, original: str, lowered: str) -> bool:
        keywords = self.REPORT_KEYWORDS
        if "earnings" in lowered and any(pattern in lowered for pattern in self.REPORT_SUPPRESSION_PATTERNS):
            keywords = keywords - {"earnings"}
        return self._contains_any(original, lowered, keywords)

    def _clean_query(self, query: str) -> str:
        lines = [line for line in query.splitlines() if not line.strip().startswith("[Hint:")]
        return "\n".join(lines).strip()

    def _extract_symbols(self, query: str) -> List[str]:
        symbols = [TickerMapper.normalize(symbol) for symbol in QueryEnricher.extract_symbols(query)]
        if symbols:
            return self._dedupe_symbols(symbols)

        inline_symbols = re.findall(r"(?<![A-Za-z])([A-Z]{2,5}(?:\.[A-Z]{1,3})?|\^[A-Z]{1,5})(?![A-Za-z])", query)
        if inline_symbols:
            normalized = [TickerMapper.normalize(symbol) for symbol in inline_symbols]
            return self._dedupe_symbols(normalized)

        matched: List[str] = []
        lowered = query.lower()
        for alias, symbol in TickerMapper.EXACT_MAP.items():
            if alias.lower() in lowered:
                matched.append(symbol)
        return self._dedupe_symbols(matched)

    def _extract_days(self, original: str, lowered: str) -> Optional[int]:
        patterns = (
            (re.search(r"(\d+)\s*天", original), 1),
            (re.search(r"(\d+)\s*day(?:s)?", lowered), 1),
            (re.search(r"(\d+)\s*周", original), 7),
            (re.search(r"(\d+)\s*week(?:s)?", lowered), 7),
            (re.search(r"(\d+)\s*个?月", original), 30),
            (re.search(r"(\d+)\s*month(?:s)?", lowered), 30),
        )
        for match, multiplier in patterns:
            if match:
                return int(match.group(1)) * multiplier
        return None

    def _extract_range(self, original: str, lowered: str) -> Optional[str]:
        for key, value in self.RANGE_MAP.items():
            if key in original or key in lowered:
                return value
        return None

    def _dedupe_symbols(self, symbols: List[str]) -> List[str]:
        unique: List[str] = []
        seen = set()
        for symbol in symbols:
            if symbol in self.NON_TICKER_UPPERCASE:
                continue
            if symbol not in seen:
                unique.append(symbol)
                seen.add(symbol)
        return unique

    @staticmethod
    def _contains_any(original: str, lowered: str, keywords: Set[str]) -> bool:
        return any(QueryRouter._keyword_present(original, lowered, keyword) for keyword in keywords)

    @staticmethod
    def _keyword_present(original: str, lowered: str, keyword: str) -> bool:
        normalized_keyword = keyword.lower()
        if normalized_keyword.isascii() and normalized_keyword.replace("-", "").replace("/", "").isalnum() and " " not in normalized_keyword:
            pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized_keyword)}(?![A-Za-z0-9])"
            return re.search(pattern, lowered) is not None
        return keyword in original or normalized_keyword in lowered
