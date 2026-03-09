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
        "etf",
        "债券",
        "bond",
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
    CHANGE_KEYWORDS = {"涨跌", "涨幅", "跌幅", "表现", "走势", "trend", "performance", "回报", "收益率"}
    HISTORY_KEYWORDS = {"历史", "k线", "chart", "走势", "trend", "ytd", "1年", "5年", "1y", "5y"}
    INFO_KEYWORDS = {"市值", "市盈率", "pe", "行业", "sector", "industry", "基本面", "信息"}
    METRIC_KEYWORDS = {"波动率", "收益率", "最大回撤", "回撤", "volatility", "return", "drawdown", "sharpe"}
    REPORT_KEYWORDS = {"季度", "财报", "业绩", "earnings", "10-k", "10-q", "8-k", "filing", "sec", "edgar"}
    COMPARE_KEYWORDS = {"对比", "比较", "哪个好", "vs", "versus", "compare"}
    ADVICE_KEYWORDS = {
        "可以买",
        "值得买吗",
        "该买吗",
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
    }
    RANGE_MAP = {
        "ytd": "ytd",
        "年初至今": "ytd",
        "今年以来": "ytd",
        "1年": "1y",
        "一年": "1y",
        "1y": "1y",
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

    async def classify_async(self, query: str) -> QueryRoute:
        return self.classify(query)

    def classify(self, query: str) -> QueryRoute:
        cleaned = self._clean_query(query)
        lowered = cleaned.lower()
        symbols = self._extract_symbols(cleaned)
        days = self._extract_days(cleaned)
        range_key = self._extract_range(cleaned, lowered)

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
            range_key=range_key,
        )

        route.requires_comparison = len(symbols) >= 2 or self._contains_any(cleaned, lowered, self.COMPARE_KEYWORDS)
        route.requires_metrics = self._contains_any(cleaned, lowered, self.METRIC_KEYWORDS)
        route.refuses_advice = self._contains_any(cleaned, lowered, self.ADVICE_KEYWORDS)

        if route_type == QueryType.MARKET:
            route.requires_price = self._contains_any(cleaned, lowered, self.CURRENT_PRICE_KEYWORDS) or not self._contains_any(
                cleaned,
                lowered,
                self.CHANGE_KEYWORDS | self.HISTORY_KEYWORDS | self.INFO_KEYWORDS | self.METRIC_KEYWORDS,
            )
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

        return route

    def _clean_query(self, query: str) -> str:
        lines = [line for line in query.splitlines() if not line.strip().startswith("[Hint:")]
        return "\n".join(lines).strip()

    def _extract_symbols(self, query: str) -> List[str]:
        symbols = [TickerMapper.normalize(symbol) for symbol in QueryEnricher.extract_symbols(query)]
        if symbols:
            return list(dict.fromkeys(symbols))

        inline_symbols = re.findall(r"(?<![A-Za-z])([A-Z]{2,5}(?:\.[A-Z]{1,3})?|\^[A-Z]{1,5})(?![A-Za-z])", query)
        if inline_symbols:
            return list(dict.fromkeys(TickerMapper.normalize(symbol) for symbol in inline_symbols))

        matched: List[str] = []
        for alias, symbol in TickerMapper.EXACT_MAP.items():
            if alias in query:
                matched.append(symbol)
        return list(dict.fromkeys(matched))

    def _extract_days(self, query: str) -> Optional[int]:
        day_match = re.search(r"(\d+)\s*天", query)
        if day_match:
            return int(day_match.group(1))

        week_match = re.search(r"(\d+)\s*周", query)
        if week_match:
            return int(week_match.group(1)) * 7

        month_match = re.search(r"(\d+)\s*(月|个月)", query)
        if month_match:
            return int(month_match.group(1)) * 30

        return None

    def _extract_range(self, original: str, lowered: str) -> Optional[str]:
        for key, value in self.RANGE_MAP.items():
            if key in original or key in lowered:
                return value
        return None

    @staticmethod
    def _contains_any(original: str, lowered: str, keywords: set[str]) -> bool:
        return any(keyword in original or keyword in lowered for keyword in keywords)
