"""Market data service with cache and provider fallback."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import redis
import yfinance as yf

from app.config import settings
from app.models import ChangeData, CompanyInfo, HistoryData, MarketData, PricePoint


TREND_UP = "\u4e0a\u6da8"
TREND_DOWN = "\u4e0b\u8dcc"
TREND_FLAT = "\u9707\u8361"


class TickerMapper:
    """Maps company names and aliases to ticker symbols."""

    EXACT_MAP = {
        "阿里巴巴": "BABA",
        "苹果": "AAPL",
        "腾讯": "0700.HK",
        "特斯拉": "TSLA",
        "比特币": "BTC-USD",
        "以太坊": "ETH-USD",
        "贵州茅台": "600519.SS",
        "茅台": "600519.SS",
        "闃块噷宸村反": "BABA",
        "鑻规灉": "AAPL",
        "鑵捐": "0700.HK",
        "鐗规柉鎷夛細": "TSLA",
        "鐗规柉鎷?": "TSLA",
        "姣旂壒甯?": "BTC-USD",
        "浠ュお鍧?": "ETH-USD",
        "璐靛窞鑼呭彴": "600519.SS",
        "鑼呭彴": "600519.SS",
    }

    @classmethod
    def normalize(cls, symbol: str) -> str:
        if not symbol:
            return ""

        normalized = symbol.strip()
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
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        self.ticker_mapper = TickerMapper()

    def _get_cache(self, key: str) -> Optional[dict]:
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    def _set_cache(self, key: str, value: dict, ttl: int):
        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    @staticmethod
    def _utc_now() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _safe_days(days: int, default: int = 30) -> int:
        try:
            normalized = abs(int(days))
        except (TypeError, ValueError):
            normalized = default
        return normalized if normalized > 0 else default

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

    async def _fetch_yfinance_history(self, symbol: str, days: int):
        ticker = await self._fetch_yfinance(symbol)
        if not ticker:
            return None

        try:
            return await asyncio.to_thread(lambda: ticker.history(period=f"{days}d"))
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

    async def _fetch_alpha_vantage_quote(self, symbol: str) -> Optional[MarketData]:
        data = await self._request_alpha_vantage("GLOBAL_QUOTE", symbol)
        if not data or "Global Quote" not in data:
            return None

        quote = data["Global Quote"] or {}
        raw_price = quote.get("05. price")
        if not raw_price:
            return None

        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None

        return MarketData(
            symbol=symbol,
            price=price,
            currency="USD",
            name=symbol,
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage(self, symbol: str) -> Optional[MarketData]:
        """Backward-compatible alias for quote fallback tests and older callers."""
        return await self._fetch_alpha_vantage_quote(symbol)

    async def _fetch_alpha_vantage_history(self, symbol: str, days: int) -> Optional[HistoryData]:
        data = await self._request_alpha_vantage("TIME_SERIES_DAILY", symbol, outputsize="compact")
        series = data.get("Time Series (Daily)") if data else None
        if not series:
            return None

        sorted_rows = sorted(series.items(), reverse=False)[-days:]
        points = []
        for trade_date, values in sorted_rows:
            try:
                points.append(
                    PricePoint(
                        date=trade_date,
                        open=float(values["1. open"]),
                        high=float(values["2. high"]),
                        low=float(values["3. low"]),
                        close=float(values["4. close"]),
                        volume=int(float(values["5. volume"])),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        if not points:
            return None

        return HistoryData(
            symbol=symbol,
            days=days,
            data=points,
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_info(self, symbol: str) -> Optional[CompanyInfo]:
        data = await self._request_alpha_vantage("OVERVIEW", symbol)
        if not data or not data.get("Symbol"):
            return None

        market_cap = data.get("MarketCapitalization")
        pe_ratio = data.get("PERatio")
        return CompanyInfo(
            symbol=symbol,
            name=data.get("Name") or symbol,
            sector=data.get("Sector"),
            industry=data.get("Industry"),
            market_cap=int(market_cap) if market_cap and market_cap.isdigit() else None,
            pe_ratio=float(pe_ratio) if pe_ratio and pe_ratio not in {"None", "-"} else None,
            week_52_high=float(data["52WeekHigh"]) if data.get("52WeekHigh") not in {None, "None", "-"} else None,
            week_52_low=float(data["52WeekLow"]) if data.get("52WeekLow") not in {None, "None", "-"} else None,
            description=(data.get("Description") or "")[:300],
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def get_price(self, symbol: str) -> MarketData:
        normalized = self.ticker_mapper.normalize(symbol)
        if not normalized:
            return MarketData(
                symbol="",
                source="unavailable",
                timestamp=self._utc_now(),
                error="Invalid symbol",
            )

        cache_key = f"price:{normalized}"
        cached = self._get_cache(cache_key)
        if cached:
            return MarketData(**cached)

        info = await self._fetch_yfinance_info(normalized)
        if info:
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price:
                result = MarketData(
                    symbol=normalized,
                    price=float(price),
                    currency=info.get("currency", "USD"),
                    name=info.get("longName") or info.get("shortName") or normalized,
                    source="yfinance",
                    timestamp=self._utc_now(),
                )
                self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_PRICE)
                return result

        fallback = await self._fetch_alpha_vantage_quote(normalized)
        if fallback:
            self._set_cache(cache_key, fallback.model_dump(), settings.CACHE_TTL_PRICE)
            return fallback

        return MarketData(
            symbol=normalized,
            source="unavailable",
            timestamp=self._utc_now(),
            error="Data unavailable from all sources",
        )

    async def get_history(self, symbol: str, days: int = 30) -> HistoryData:
        normalized = self.ticker_mapper.normalize(symbol)
        safe_days = self._safe_days(days)
        cache_key = f"history:{normalized}:{safe_days}"

        cached = self._get_cache(cache_key)
        if cached:
            return HistoryData(**cached)

        hist = await self._fetch_yfinance_history(normalized, safe_days)
        if hist is not None and not hist.empty:
            data = [
                PricePoint(
                    date=index.strftime("%Y-%m-%d"),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
                for index, row in hist.iterrows()
            ]

            result = HistoryData(
                symbol=normalized,
                days=safe_days,
                data=data,
                source="yfinance",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_HISTORY)
            return result

        fallback = await self._fetch_alpha_vantage_history(normalized, safe_days)
        if fallback:
            self._set_cache(cache_key, fallback.model_dump(), settings.CACHE_TTL_HISTORY)
            return fallback

        return HistoryData(
            symbol=normalized,
            days=safe_days,
            data=[],
            source="unavailable",
            timestamp=self._utc_now(),
        )

    async def get_change(self, symbol: str, days: int = 7) -> ChangeData:
        normalized = self.ticker_mapper.normalize(symbol)
        safe_days = self._safe_days(days, default=7)
        cache_key = f"change:{normalized}:{safe_days}"

        cached = self._get_cache(cache_key)
        if cached:
            return ChangeData(**cached)

        history = await self.get_history(normalized, safe_days)
        if len(history.data) >= 2:
            start_price = history.data[0].close
            end_price = history.data[-1].close
            change_pct = ((end_price - start_price) / start_price) * 100 if start_price else 0

            if change_pct > 2:
                trend = TREND_UP
            elif change_pct < -2:
                trend = TREND_DOWN
            else:
                trend = TREND_FLAT

            result = ChangeData(
                symbol=normalized,
                days=safe_days,
                start_price=start_price,
                end_price=end_price,
                change_pct=round(change_pct, 2),
                trend=trend,
                source=history.source,
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_PRICE)
            return result

        return ChangeData(
            symbol=normalized,
            days=safe_days,
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
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                week_52_high=info.get("fiftyTwoWeekHigh"),
                week_52_low=info.get("fiftyTwoWeekLow"),
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

        return CompanyInfo(
            symbol=normalized,
            name=normalized or symbol,
            source="unavailable",
            timestamp=self._utc_now(),
        )

    def check_cache(self) -> bool:
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False
