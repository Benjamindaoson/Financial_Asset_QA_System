"""Market data service with cache, analytics, and provider fallback."""

from __future__ import annotations

import asyncio
import csv
import json
import math
from datetime import datetime, timedelta
from io import StringIO
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx
import numpy as np
import redis
import yfinance as yf

from app.cache.popular_stocks import get_popular_stocks
from app.config import settings
from app.market.api_providers import NewsAPIProvider, FinnhubProvider
from app.models import (
    ChangeData,
    CompanyInfo,
    ComparisonData,
    ComparisonPoint,
    ComparisonRow,
    HistoryData,
    MarketData,
    MarketIndexSnapshot,
    MarketOverviewResponse,
    MarketSignal,
    MarketSummary,
    PricePoint,
    RiskMetrics,
    SectorSnapshot,
)


TREND_UP = "上涨"
TREND_DOWN = "下跌"
TREND_FLAT = "震荡"

RANGE_TO_DAYS = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "ytd": 365,
    "1y": 365,
    "5y": 365 * 5,
}

INDEX_WATCHLIST = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "NASDAQ"),
    ("^DJI", "Dow Jones"),
    ("^VIX", "VIX"),
    ("BND", "US Bond ETF"),
]

SECTOR_WATCHLIST = [
    ("XLK", "Technology"),
    ("XLF", "Financials"),
    ("XLE", "Energy"),
    ("XLV", "Healthcare"),
    ("XLY", "Consumer Discretionary"),
    ("XLI", "Industrials"),
]


class TickerMapper:
    """Maps company names and common aliases to ticker symbols."""

    EXACT_MAP = {
        "阿里巴巴": "BABA",
        "苹果": "AAPL",
        "腾讯": "0700.HK",
        "特斯拉": "TSLA",
        "英伟达": "NVDA",
        "微软": "MSFT",
        "亚马逊": "AMZN",
        "谷歌": "GOOGL",
        "茅台": "600519.SS",
        "贵州茅台": "600519.SS",
        "比亚迪": "002594.SZ",
        "纳指": "^IXIC",
        "标普500": "^GSPC",
        "道琼斯": "^DJI",
        "波动率指数": "^VIX",
        "vix": "^VIX",
        "比特币": "BTC-USD",
        "以太坊": "ETH-USD",
        "黄金etf": "GLD",
        "原油etf": "USO",
        "债券": "BND",
        "债券etf": "BND",
        "美国国债": "TLT",
        "10年期美债": "^TNX",
        "20年期美债": "TLT",
        "7-10年美债": "IEF",
        "短债": "SHY",
        "总债券市场": "BND",
        "纳斯达克100": "QQQ",
        "标普etf": "SPY",
    }

    @classmethod
    def normalize(cls, symbol: str) -> str:
        if not symbol:
            return ""

        normalized = symbol.strip()
        if not normalized:
            return ""

        lowered = normalized.lower()
        if lowered in cls.EXACT_MAP:
            return cls.EXACT_MAP[lowered]
        if normalized in cls.EXACT_MAP:
            return cls.EXACT_MAP[normalized]

        if normalized.isdigit() and len(normalized) == 6:
            if normalized.startswith("6"):
                return f"{normalized}.SS"
            if normalized.startswith(("0", "3")):
                return f"{normalized}.SZ"

        return normalized.upper()


class MarketDataService:
    """Market data service with Redis caching and Alpha Vantage fallback."""

    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
        except Exception:
            self.redis_client = None
        self.ticker_mapper = TickerMapper()
        self.news_provider = NewsAPIProvider()
        self.finnhub_provider = FinnhubProvider()

    def _get_cache(self, key: str) -> Optional[dict]:
        if not self.redis_client:
            return None
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            return None
        return None

    def _set_cache(self, key: str, value: dict, ttl: int) -> None:
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
        except Exception:
            return

    @staticmethod
    def _utc_now() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _safe_days(days: Optional[int], default: int = 30) -> int:
        try:
            normalized = abs(int(days or default))
        except (TypeError, ValueError):
            normalized = default
        return normalized if normalized > 0 else default

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            if value in (None, "", "-", "None", "N/D"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            if value in (None, "", "-", "None", "N/D"):
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _range_to_period(range_key: Optional[str], days: int) -> tuple[str, int]:
        if not range_key:
            safe_days = max(7, days)
            return f"{safe_days}d", safe_days

        normalized = range_key.lower()
        if normalized not in RANGE_TO_DAYS:
            safe_days = max(7, days)
            return f"{safe_days}d", safe_days

        if normalized == "ytd":
            return "ytd", RANGE_TO_DAYS[normalized]
        return normalized, RANGE_TO_DAYS[normalized]

    @staticmethod
    def _infer_asset_type(info: Optional[dict], symbol: str) -> str:
        if not info:
            if symbol.endswith("-USD"):
                return "crypto"
            if symbol.startswith("^"):
                return "index"
            return "equity"

        quote_type = str(info.get("quoteType") or info.get("instrumentType") or "").lower()
        if "etf" in quote_type:
            return "etf"
        if "bond" in quote_type or symbol in {"BND", "TLT", "IEF", "SHY"}:
            return "bond"
        if "index" in quote_type or symbol.startswith("^"):
            return "index"
        if "currency" in quote_type or symbol.endswith("-USD"):
            return "crypto"
        return "equity"

    async def _fetch_yfinance(self, symbol: str) -> Optional[yf.Ticker]:
        try:
            return await asyncio.to_thread(yf.Ticker, symbol)
        except Exception:
            return None

    async def _fetch_yfinance_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        ticker = await self._fetch_yfinance(symbol)
        if not ticker:
            return None
        try:
            return await asyncio.to_thread(lambda: ticker.info)
        except Exception:
            return None

    async def _fetch_yfinance_history(self, symbol: str, period: str):
        ticker = await self._fetch_yfinance(symbol)
        if not ticker:
            return None
        try:
            return await asyncio.to_thread(lambda: ticker.history(period=period, auto_adjust=False))
        except Exception:
            return None

    async def _request_alpha_vantage(self, function: str, symbol: str, **extra_params) -> Optional[dict]:
        if not settings.ALPHA_VANTAGE_API_KEY:
            return None

        params = {
            "function": function,
            "symbol": symbol,
            "apikey": settings.ALPHA_VANTAGE_API_KEY,
        }
        params.update(extra_params)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://www.alphavantage.co/query", params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                if "Error Message" in data or "Note" in data or "Information" in data:
                    return None
                return data
        except Exception:
            return None

    def _to_stooq_symbol(self, symbol: str) -> Optional[str]:
        normalized = symbol.upper()
        index_map = {
            "^GSPC": "^spx",
            "^IXIC": "^ndq",
            "^DJI": "^dji",
            "^VIX": "^vix",
        }
        if normalized in index_map:
            return index_map[normalized]
        if normalized.endswith(".HK"):
            return f"{normalized[:-3].lower()}.hk"
        if normalized.endswith(".SS") or normalized.endswith(".SZ"):
            return f"{normalized[:6].lower()}.cn"
        if normalized.endswith("-USD"):
            return None
        if normalized.startswith("^"):
            return normalized.lower()
        return f"{normalized.lower()}.us"

    async def _request_stooq(self, endpoint: str, symbol: str) -> Optional[str]:
        stooq_symbol = self._to_stooq_symbol(symbol)
        if not stooq_symbol:
            return None

        for _ in range(2):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(
                        f"https://stooq.com/{endpoint}?s={stooq_symbol}&i=d",
                        follow_redirects=True,
                    )
                    if response.status_code == 200 and response.text.strip():
                        return response.text
            except Exception:
                continue
        return None

    async def _fetch_stooq_quote(self, symbol: str) -> Optional[MarketData]:
        raw = await self._request_stooq("q/l/", symbol)
        if not raw:
            return None

        rows = list(csv.reader(StringIO(raw)))
        if not rows:
            return None
        row = rows[0]
        if len(row) < 8 or row[1] == "N/D":
            return None

        price = self._coerce_float(row[6])
        if price is None:
            return None

        return MarketData(
            symbol=symbol,
            price=price,
            currency="USD",
            name=symbol,
            asset_type=self._infer_asset_type(None, symbol),
            source="stooq",
            timestamp=self._utc_now(),
        )

    async def _fetch_stooq_history(self, symbol: str, days: int, range_key: Optional[str] = None) -> Optional[HistoryData]:
        raw = await self._request_stooq("q/d/l/", symbol)
        if not raw:
            return None

        rows = list(csv.DictReader(StringIO(raw)))
        rows = [row for row in rows if row.get("Date")]
        if not rows:
            return None

        if range_key == "5y":
            limit = 365 * 5
        elif range_key == "1y":
            limit = 365
        elif range_key == "ytd":
            current_year = datetime.utcnow().year
            rows = [row for row in rows if row["Date"].startswith(str(current_year))]
            limit = len(rows)
        else:
            limit = days

        selected = rows[-max(limit, 1):]
        points: List[PricePoint] = []
        for row in selected:
            open_price = self._coerce_float(row.get("Open"))
            high = self._coerce_float(row.get("High"))
            low = self._coerce_float(row.get("Low"))
            close = self._coerce_float(row.get("Close"))
            volume = self._coerce_int(row.get("Volume")) or 0
            if None in {open_price, high, low, close}:
                continue
            points.append(
                PricePoint(
                    date=row["Date"],
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )

        if not points:
            return None

        return HistoryData(
            symbol=symbol,
            days=days,
            range_key=range_key,
            data=points,
            source="stooq",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_quote(self, symbol: str) -> Optional[MarketData]:
        data = await self._request_alpha_vantage("GLOBAL_QUOTE", symbol)
        quote = data.get("Global Quote") if data else None
        if not quote:
            return None

        price = self._coerce_float(quote.get("05. price"))
        if price is None:
            return None

        return MarketData(
            symbol=symbol,
            price=price,
            currency="USD",
            name=symbol,
            asset_type="equity",
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_history(self, symbol: str, days: int, range_key: Optional[str] = None) -> Optional[HistoryData]:
        outputsize = "full" if (range_key or "").lower() == "5y" or days > 100 else "compact"
        data = await self._request_alpha_vantage("TIME_SERIES_DAILY", symbol, outputsize=outputsize)
        series = data.get("Time Series (Daily)") if data else None
        if not series:
            return None

        sorted_rows = sorted(series.items())[-days:]
        points: List[PricePoint] = []
        for trade_date, values in sorted_rows:
            open_price = self._coerce_float(values.get("1. open"))
            high = self._coerce_float(values.get("2. high"))
            low = self._coerce_float(values.get("3. low"))
            close = self._coerce_float(values.get("4. close"))
            volume = self._coerce_int(values.get("5. volume")) or 0
            if None in {open_price, high, low, close}:
                continue
            points.append(
                PricePoint(
                    date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )

        if not points:
            return None

        return HistoryData(
            symbol=symbol,
            days=len(points),
            range_key=range_key,
            data=points,
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_info(self, symbol: str) -> Optional[CompanyInfo]:
        data = await self._request_alpha_vantage("OVERVIEW", symbol)
        if not data or not data.get("Symbol"):
            return None

        return CompanyInfo(
            symbol=symbol,
            name=data.get("Name") or symbol,
            sector=data.get("Sector"),
            industry=data.get("Industry"),
            market_cap=self._coerce_int(data.get("MarketCapitalization")),
            pe_ratio=self._coerce_float(data.get("PERatio")),
            week_52_high=self._coerce_float(data.get("52WeekHigh")),
            week_52_low=self._coerce_float(data.get("52WeekLow")),
            description=(data.get("Description") or "")[:300],
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    def _history_to_points(self, history_frame: Any) -> List[PricePoint]:
        points: List[PricePoint] = []
        if history_frame is None or getattr(history_frame, "empty", True):
            return points

        for index, row in history_frame.iterrows():
            open_price = self._coerce_float(row.get("Open"))
            high = self._coerce_float(row.get("High"))
            low = self._coerce_float(row.get("Low"))
            close = self._coerce_float(row.get("Close"))
            volume = self._coerce_int(row.get("Volume")) or 0
            if None in {open_price, high, low, close}:
                continue
            points.append(
                PricePoint(
                    date=index.strftime("%Y-%m-%d"),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        return points

    async def get_price(self, symbol: str) -> MarketData:
        start_time = datetime.utcnow()
        normalized = self.ticker_mapper.normalize(symbol)
        if not normalized:
            return MarketData(symbol="", source="unavailable", timestamp=self._utc_now(), error="Invalid symbol")

        cache_key = f"price:{normalized}"
        cached = self._get_cache(cache_key)
        if cached:
            result = MarketData(**cached)
            result.cache_hit = True
            result.latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return result

        info = await self._fetch_yfinance_info(normalized)
        if info:
            price = self._coerce_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            if price is not None:
                result = MarketData(
                    symbol=normalized,
                    price=price,
                    currency=info.get("currency", "USD"),
                    name=info.get("longName") or info.get("shortName") or normalized,
                    asset_type=self._infer_asset_type(info, normalized),
                    source="yfinance",
                    timestamp=self._utc_now(),
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                )
                self._set_cache(cache_key, result.model_dump(exclude={"cache_hit", "latency_ms"}), settings.CACHE_TTL_PRICE)
                return result

        fallback = await self._fetch_stooq_quote(normalized)
        if not fallback:
            fallback = await self._fetch_alpha_vantage_quote(normalized)
        if fallback:
            fallback.latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._set_cache(cache_key, fallback.model_dump(exclude={"cache_hit", "latency_ms"}), settings.CACHE_TTL_PRICE)
            return fallback

        return MarketData(
            symbol=normalized,
            source="unavailable",
            timestamp=self._utc_now(),
            error="Data unavailable from all sources",
            latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
        )

    async def get_history(self, symbol: str, days: int = 30, range_key: Optional[str] = None) -> HistoryData:
        normalized = self.ticker_mapper.normalize(symbol)
        period, normalized_days = self._range_to_period(range_key, self._safe_days(days))
        cache_key = f"history:{normalized}:{range_key or normalized_days}"
        cached = self._get_cache(cache_key)
        if cached:
            return HistoryData(**cached)

        hist = await self._fetch_yfinance_history(normalized, period)
        points = self._history_to_points(hist)
        if points:
            result = HistoryData(
                symbol=normalized,
                days=normalized_days,
                range_key=range_key,
                data=points,
                source="yfinance",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_HISTORY)
            return result

        fallback = await self._fetch_stooq_history(normalized, normalized_days, range_key=range_key)
        if not fallback:
            fallback = await self._fetch_alpha_vantage_history(normalized, normalized_days, range_key=range_key)
        if fallback:
            self._set_cache(cache_key, fallback.model_dump(), settings.CACHE_TTL_HISTORY)
            return fallback

        return HistoryData(
            symbol=normalized,
            days=normalized_days,
            range_key=range_key,
            data=[],
            source="unavailable",
            timestamp=self._utc_now(),
        )

    async def get_change(self, symbol: str, days: int = 7, range_key: Optional[str] = None) -> ChangeData:
        normalized = self.ticker_mapper.normalize(symbol)
        history = await self.get_history(normalized, days=days, range_key=range_key)
        if len(history.data) >= 2:
            start_price = history.data[0].close
            end_price = history.data[-1].close
            change_pct = ((end_price - start_price) / start_price) * 100 if start_price else 0.0
            if change_pct > 1:
                trend = TREND_UP
            elif change_pct < -1:
                trend = TREND_DOWN
            else:
                trend = TREND_FLAT
            return ChangeData(
                symbol=normalized,
                days=self._safe_days(days, default=7),
                start_price=start_price,
                end_price=end_price,
                change_pct=round(change_pct, 2),
                trend=trend,
                source=history.source,
                timestamp=self._utc_now(),
            )

        return ChangeData(
            symbol=normalized,
            days=days,
            start_price=0,
            end_price=0,
            change_pct=0,
            trend=TREND_FLAT,
            source="unavailable",
            timestamp=self._utc_now(),
        )

    async def get_info(self, symbol: str) -> CompanyInfo:
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"info:{normalized}"
        cached = self._get_cache(cache_key)
        if cached:
            return CompanyInfo(**cached)

        info = await self._fetch_yfinance_info(normalized)
        if info:
            result = CompanyInfo(
                symbol=normalized,
                name=info.get("longName") or info.get("shortName") or normalized,
                sector=info.get("sector"),
                industry=info.get("industry"),
                market_cap=self._coerce_int(info.get("marketCap")),
                pe_ratio=self._coerce_float(info.get("trailingPE")),
                week_52_high=self._coerce_float(info.get("fiftyTwoWeekHigh")),
                week_52_low=self._coerce_float(info.get("fiftyTwoWeekLow")),
                description=(info.get("longBusinessSummary") or "")[:300],
                source="yfinance",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(by_alias=True), settings.CACHE_TTL_INFO)
            return result

        fallback = await self._fetch_alpha_vantage_info(normalized)
        if fallback:
            self._set_cache(cache_key, fallback.model_dump(by_alias=True), settings.CACHE_TTL_INFO)
            return fallback

        return CompanyInfo(symbol=normalized, name=normalized or symbol, source="unavailable", timestamp=self._utc_now())

    async def get_metrics(self, symbol: str, range_key: str = "1y") -> RiskMetrics:
        normalized = self.ticker_mapper.normalize(symbol)
        history = await self.get_history(normalized, days=RANGE_TO_DAYS.get(range_key, 365), range_key=range_key)
        if len(history.data) < 2:
            stooq_retry = await self._fetch_stooq_history(normalized, RANGE_TO_DAYS.get(range_key, 365), range_key=range_key)
            if stooq_retry and len(stooq_retry.data) >= 2:
                history = stooq_retry
            else:
                fallback_history = await self.get_history(normalized, days=365)
                if len(fallback_history.data) >= 2:
                    history = fallback_history
        if len(history.data) < 2:
            return RiskMetrics(
                symbol=normalized,
                range_key=range_key,
                source=history.source,
                timestamp=self._utc_now(),
                error="Insufficient history for metrics",
            )

        closes = np.array([point.close for point in history.data], dtype=float)
        returns = np.diff(closes) / closes[:-1]
        if returns.size == 0:
            return RiskMetrics(
                symbol=normalized,
                range_key=range_key,
                source=history.source,
                timestamp=self._utc_now(),
                error="Insufficient returns for metrics",
            )

        total_return = ((closes[-1] / closes[0]) - 1.0) * 100
        cumulative = np.cumprod(1.0 + returns)
        running_peak = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative / running_peak) - 1.0
        max_drawdown = float(drawdowns.min()) * 100 if drawdowns.size else 0.0
        volatility = float(np.std(returns, ddof=1)) * math.sqrt(252) * 100 if returns.size > 1 else 0.0
        annualized_return = (float(np.prod(1.0 + returns)) ** (252 / max(len(returns), 1)) - 1.0) * 100
        sharpe_ratio = (annualized_return / volatility) if volatility else None

        return RiskMetrics(
            symbol=normalized,
            range_key=range_key,
            annualized_volatility=round(volatility, 2),
            total_return_pct=round(total_return, 2),
            max_drawdown_pct=round(max_drawdown, 2),
            annualized_return_pct=round(annualized_return, 2),
            sharpe_ratio=round(sharpe_ratio, 2) if sharpe_ratio is not None else None,
            source=history.source,
            timestamp=self._utc_now(),
        )

    async def compare_assets(self, symbols: Sequence[str], range_key: str = "1y") -> ComparisonData:
        normalized_symbols = [self.ticker_mapper.normalize(symbol) for symbol in symbols[:4] if symbol]
        if not normalized_symbols:
            return ComparisonData(symbols=[], range_key=range_key, rows=[], chart=[], source="unavailable", timestamp=self._utc_now())

        prices_task = [self.get_price(symbol) for symbol in normalized_symbols]
        metrics_task = [self.get_metrics(symbol, range_key=range_key) for symbol in normalized_symbols]
        history_task = [
            self.get_history(symbol, days=RANGE_TO_DAYS.get(range_key, 365), range_key=range_key) for symbol in normalized_symbols
        ]
        prices, metrics, histories = await asyncio.gather(
            asyncio.gather(*prices_task),
            asyncio.gather(*metrics_task),
            asyncio.gather(*history_task),
        )

        repaired_histories: List[HistoryData] = []
        for symbol, history in zip(normalized_symbols, histories):
            if history.data:
                repaired_histories.append(history)
                continue
            fallback_history = await self._fetch_stooq_history(symbol, RANGE_TO_DAYS.get(range_key, 365), range_key=range_key)
            repaired_histories.append(fallback_history or history)
        histories = repaired_histories

        rows: List[ComparisonRow] = []
        for symbol, price, metric in zip(normalized_symbols, prices, metrics):
            rows.append(
                ComparisonRow(
                    symbol=symbol,
                    name=price.name,
                    price=price.price,
                    total_return_pct=metric.total_return_pct,
                    annualized_volatility=metric.annualized_volatility,
                    max_drawdown_pct=metric.max_drawdown_pct,
                    source=f"{price.source}/{metric.source}",
                    timestamp=metric.timestamp,
                )
            )

        chart = self._build_comparison_chart(normalized_symbols, histories)
        sources = {history.source for history in histories if history.source}
        return ComparisonData(
            symbols=normalized_symbols,
            range_key=range_key,
            rows=rows,
            chart=chart,
            source="/".join(sorted(sources)) if sources else "unavailable",
            timestamp=self._utc_now(),
        )

    def _build_comparison_chart(self, symbols: Sequence[str], histories: Sequence[HistoryData]) -> List[ComparisonPoint]:
        valid_histories = [history for history in histories if history.data]
        if not valid_histories:
            return []

        common_dates = set(point.date for point in valid_histories[0].data)
        for history in valid_histories[1:]:
            common_dates &= {point.date for point in history.data}
        if not common_dates:
            return []

        ordered_dates = sorted(common_dates)
        per_symbol: Dict[str, Dict[str, float]] = {}
        base_price: Dict[str, float] = {}
        for symbol, history in zip(symbols, histories):
            mapping = {point.date: point.close for point in history.data if point.date in common_dates}
            if not mapping:
                continue
            first_date = ordered_dates[0]
            if first_date not in mapping:
                continue
            per_symbol[symbol] = mapping
            base_price[symbol] = mapping[first_date]

        chart: List[ComparisonPoint] = []
        for trade_date in ordered_dates:
            values: Dict[str, float] = {}
            for symbol, mapping in per_symbol.items():
                base = base_price.get(symbol) or 0
                if trade_date in mapping and base:
                    values[symbol] = round(mapping[trade_date] / base * 100, 2)
            if values:
                chart.append(ComparisonPoint(date=trade_date, values=values))
        return chart

    async def get_market_overview(self) -> MarketOverviewResponse:
        index_payload = await asyncio.gather(*[self._build_index_snapshot(symbol, name) for symbol, name in INDEX_WATCHLIST])
        sector_payload = await asyncio.gather(*[self._build_sector_snapshot(symbol, name) for symbol, name in SECTOR_WATCHLIST])
        signals = await self._build_market_signals()
        summary = self._build_market_summary(index_payload, signals, sector_payload)
        return MarketOverviewResponse(indices=index_payload, signals=signals, sectors=sector_payload, summary=summary)

    async def _build_index_snapshot(self, symbol: str, display_name: str) -> MarketIndexSnapshot:
        price, change = await asyncio.gather(self.get_price(symbol), self.get_change(symbol, days=5))
        return MarketIndexSnapshot(
            symbol=price.symbol or symbol,
            name=display_name,
            price=price.price,
            change_pct=change.change_pct,
            source=f"{price.source}/{change.source}",
            timestamp=price.timestamp,
        )

    async def _build_sector_snapshot(self, symbol: str, display_name: str) -> SectorSnapshot:
        change = await self.get_change(symbol, days=5)
        return SectorSnapshot(
            name=display_name,
            symbol=symbol,
            change_pct=change.change_pct,
            source=change.source,
            timestamp=change.timestamp,
        )

    async def _build_market_signals(self) -> List[MarketSignal]:
        candidates = get_popular_stocks(limit=10)
        histories = await asyncio.gather(*[self.get_history(symbol, days=30) for symbol in candidates])
        signals: List[MarketSignal] = []
        for symbol, history in zip(candidates, histories):
            if len(history.data) < 5:
                continue
            closes = np.array([point.close for point in history.data], dtype=float)
            volumes = np.array([point.volume for point in history.data], dtype=float)
            change_pct = ((closes[-1] / closes[-5]) - 1.0) * 100 if closes[-5] else 0.0
            avg_volume = float(volumes[:-1].mean()) if len(volumes) > 1 else float(volumes[-1])
            volume_ratio = (volumes[-1] / avg_volume) if avg_volume else 1.0
            volatility = float(np.std(np.diff(closes) / closes[:-1], ddof=1)) * math.sqrt(252) * 100 if len(closes) > 2 else 0.0
            signal_type = "price_spike"
            if volume_ratio >= 1.8:
                signal_type = "volume_spike"
            elif volatility >= 40:
                signal_type = "volatility"

            score = min(99, int(abs(change_pct) * 6 + max(volume_ratio - 1, 0) * 20 + volatility * 0.2))
            if score < 45:
                continue
            signals.append(
                MarketSignal(
                    symbol=TickerMapper.normalize(symbol),
                    change_pct=round(change_pct, 2),
                    signal_type=signal_type,
                    signal_score=score,
                    volume_ratio=round(volume_ratio, 2),
                    source=history.source,
                    timestamp=history.timestamp,
                )
            )
        signals.sort(key=lambda item: item.signal_score, reverse=True)
        return signals[:5]

    def _build_market_summary(
        self,
        indices: Iterable[MarketIndexSnapshot],
        signals: Iterable[MarketSignal],
        sectors: Iterable[SectorSnapshot],
    ) -> MarketSummary:
        indices = list(indices)
        signals = list(signals)
        sectors = list(sectors)

        leader = max(sectors, key=lambda item: item.change_pct, default=None)
        laggard = min(sectors, key=lambda item: item.change_pct, default=None)
        strongest_index = max(indices, key=lambda item: item.change_pct or -999, default=None)
        hottest_signal = signals[0] if signals else None

        parts: List[str] = []
        if strongest_index and strongest_index.change_pct is not None:
            parts.append(f"{strongest_index.name} 近5日变动 {strongest_index.change_pct:+.2f}%。")
        if leader and laggard:
            parts.append(f"板块表现方面，{leader.name} 领先 {leader.change_pct:+.2f}%，{laggard.name} 相对偏弱 {laggard.change_pct:+.2f}%。")
        if hottest_signal:
            parts.append(
                f"个股信号中 {hottest_signal.symbol} 最活跃，区间涨跌 {hottest_signal.change_pct:+.2f}%，信号分 {hottest_signal.signal_score}。"
            )

        available = sum(1 for item in indices if item.price is not None)
        confidence = "高" if available >= 4 else "中" if available >= 2 else "低"
        text = " ".join(parts) if parts else "当前可用的市场数据有限，建议稍后刷新。"
        return MarketSummary(text=text, confidence=confidence)

    async def get_news(self, symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get news articles for a stock symbol. Combines results from both Finnhub and NewsAPI."""
        start_time = datetime.utcnow()
        normalized = self.ticker_mapper.normalize(symbol)
        if not normalized:
            return []

        cache_key = f"news:{normalized}:{days}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        # Call both APIs in parallel
        finnhub_task = self.finnhub_provider.get_news(normalized, from_date=from_str, to_date=to_str)
        newsapi_task = self.news_provider.get_stock_news(normalized, days=days, page_size=10)

        finnhub_news, newsapi_news = await asyncio.gather(finnhub_task, newsapi_task, return_exceptions=True)

        all_news = []

        # Process Finnhub news
        if finnhub_news and not isinstance(finnhub_news, Exception):
            for article in finnhub_news[:10]:  # Limit to 10 articles
                all_news.append({
                    "title": article.get("headline"),
                    "description": article.get("summary"),
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "published_at": datetime.fromtimestamp(article.get("datetime", 0)).isoformat() if article.get("datetime") else None,
                    "author": None,
                    "image_url": article.get("image"),
                    "provider": "finnhub"
                })

        # Process NewsAPI news
        if newsapi_news and not isinstance(newsapi_news, Exception):
            for article in newsapi_news:
                article["provider"] = "newsapi"
                all_news.append(article)

        # Sort by published date (newest first)
        all_news.sort(key=lambda x: x.get("published_at") or "", reverse=True)

        # Cache for 1 hour
        if all_news:
            self._set_cache(cache_key, all_news, ttl=3600)

        return all_news

    def check_cache(self) -> bool:
        if not self.redis_client:
            return False
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False
