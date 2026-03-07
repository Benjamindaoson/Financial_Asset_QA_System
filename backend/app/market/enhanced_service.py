"""
Enhanced market data service with multi-provider support.
Integrates: yfinance, Alpha Vantage, Finnhub, FRED, Polygon, Twelve Data, FMP, CoinGecko, Frankfurter
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

import redis
import yfinance as yf

from app.config import settings
from app.market.api_providers import MultiProviderClient
from app.models import ChangeData, CompanyInfo, HistoryData, MarketData, PricePoint


TREND_UP = "上涨"
TREND_DOWN = "下跌"
TREND_FLAT = "震荡"


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
        "微软": "MSFT",
        "谷歌": "GOOGL",
        "亚马逊": "AMZN",
        "英伟达": "NVDA",
        "Meta": "META",
        "Netflix": "NFLX",
    }

    # Crypto mapping for CoinGecko
    CRYPTO_MAP = {
        "BTC-USD": "bitcoin",
        "ETH-USD": "ethereum",
        "比特币": "bitcoin",
        "以太坊": "ethereum",
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

    @classmethod
    def is_crypto(cls, symbol: str) -> bool:
        """Check if symbol is a cryptocurrency."""
        return symbol in cls.CRYPTO_MAP or symbol.endswith("-USD")

    @classmethod
    def get_crypto_id(cls, symbol: str) -> Optional[str]:
        """Get CoinGecko coin ID from symbol."""
        return cls.CRYPTO_MAP.get(symbol)


class EnhancedMarketDataService:
    """Enhanced market data service with multi-provider support."""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        self.ticker_mapper = TickerMapper()
        self.multi_provider = MultiProviderClient()

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

    async def get_price(self, symbol: str) -> MarketData:
        """Get stock price with multi-provider fallback."""
        start_time = datetime.utcnow()
        normalized = self.ticker_mapper.normalize(symbol)
        if not normalized:
            return MarketData(
                symbol="",
                source="unavailable",
                timestamp=self._utc_now(),
                error="Invalid symbol",
                cache_hit=False,
            )

        cache_key = f"price:{normalized}"
        cached = self._get_cache(cache_key)
        if cached:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = MarketData(**cached)
            result.cache_hit = True
            result.latency_ms = latency
            return result

        # Check if it's a cryptocurrency
        if self.ticker_mapper.is_crypto(normalized):
            coin_id = self.ticker_mapper.get_crypto_id(normalized)
            if coin_id:
                crypto_data = await self.multi_provider.get_crypto_price(coin_id)
                if crypto_data:
                    latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                    result = MarketData(
                        symbol=normalized,
                        price=float(crypto_data.get("usd", 0)),
                        currency="USD",
                        name=coin_id.title(),
                        source="coingecko",
                        timestamp=self._utc_now(),
                        cache_hit=False,
                        latency_ms=latency,
                    )
                    cache_data = result.model_dump(exclude={'cache_hit', 'latency_ms'})
                    self._set_cache(cache_key, cache_data, settings.CACHE_TTL_PRICE)
                    return result

        # Try yfinance first
        info = await self._fetch_yfinance_info(normalized)
        if info:
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price:
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                result = MarketData(
                    symbol=normalized,
                    price=float(price),
                    currency=info.get("currency", "USD"),
                    name=info.get("longName") or info.get("shortName") or normalized,
                    source="yfinance",
                    timestamp=self._utc_now(),
                    cache_hit=False,
                    latency_ms=latency,
                )
                cache_data = result.model_dump(exclude={'cache_hit', 'latency_ms'})
                self._set_cache(cache_key, cache_data, settings.CACHE_TTL_PRICE)
                return result

        # Try multiple providers in parallel
        multi_quotes = await self.multi_provider.get_stock_quote_multi(normalized)

        # Try Finnhub first (best free tier)
        if "finnhub" in multi_quotes:
            fh_data = multi_quotes["finnhub"]
            if fh_data.get("c"):
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                result = MarketData(
                    symbol=normalized,
                    price=float(fh_data["c"]),
                    currency="USD",
                    name=normalized,
                    source="finnhub",
                    timestamp=self._utc_now(),
                    cache_hit=False,
                    latency_ms=latency,
                )
                cache_data = result.model_dump(exclude={'cache_hit', 'latency_ms'})
                self._set_cache(cache_key, cache_data, settings.CACHE_TTL_PRICE)
                return result

        # Try Alpha Vantage
        if "alpha_vantage" in multi_quotes:
            av_data = multi_quotes["alpha_vantage"]
            if av_data.get("05. price"):
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                result = MarketData(
                    symbol=normalized,
                    price=float(av_data["05. price"]),
                    currency="USD",
                    name=normalized,
                    source="alpha_vantage",
                    timestamp=self._utc_now(),
                    cache_hit=False,
                    latency_ms=latency,
                )
                cache_data = result.model_dump(exclude={'cache_hit', 'latency_ms'})
                self._set_cache(cache_key, cache_data, settings.CACHE_TTL_PRICE)
                return result

        # Try Twelve Data
        if "twelve_data" in multi_quotes:
            td_data = multi_quotes["twelve_data"]
            if td_data.get("close"):
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                result = MarketData(
                    symbol=normalized,
                    price=float(td_data["close"]),
                    currency=td_data.get("currency", "USD"),
                    name=td_data.get("name", normalized),
                    source="twelve_data",
                    timestamp=self._utc_now(),
                    cache_hit=False,
                    latency_ms=latency,
                )
                cache_data = result.model_dump(exclude={'cache_hit', 'latency_ms'})
                self._set_cache(cache_key, cache_data, settings.CACHE_TTL_PRICE)
                return result

        # Try FMP
        if "fmp" in multi_quotes:
            fmp_data = multi_quotes["fmp"]
            if fmp_data.get("price"):
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                result = MarketData(
                    symbol=normalized,
                    price=float(fmp_data["price"]),
                    currency="USD",
                    name=fmp_data.get("name", normalized),
                    source="fmp",
                    timestamp=self._utc_now(),
                    cache_hit=False,
                    latency_ms=latency,
                )
                cache_data = result.model_dump(exclude={'cache_hit', 'latency_ms'})
                self._set_cache(cache_key, cache_data, settings.CACHE_TTL_PRICE)
                return result

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        return MarketData(
            symbol=normalized,
            source="unavailable",
            timestamp=self._utc_now(),
            error="Data unavailable from all sources",
            cache_hit=False,
            latency_ms=latency,
        )

    async def get_history(self, symbol: str, days: int = 30) -> HistoryData:
        """Get historical data with fallback."""
        normalized = self.ticker_mapper.normalize(symbol)
        safe_days = self._safe_days(days)
        cache_key = f"history:{normalized}:{safe_days}"

        cached = self._get_cache(cache_key)
        if cached:
            return HistoryData(**cached)

        # Try yfinance first
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

        # Try Alpha Vantage fallback
        av_history = await self.multi_provider.alpha_vantage.get_daily_history(normalized)
        if av_history:
            sorted_rows = sorted(av_history.items(), reverse=False)[-safe_days:]
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

            if points:
                result = HistoryData(
                    symbol=normalized,
                    days=safe_days,
                    data=points,
                    source="alpha_vantage",
                    timestamp=self._utc_now(),
                )
                self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_HISTORY)
                return result

        return HistoryData(
            symbol=normalized,
            days=safe_days,
            data=[],
            source="unavailable",
            timestamp=self._utc_now(),
        )

    async def get_change(self, symbol: str, days: int = 7) -> ChangeData:
        """Calculate price change over period."""
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
        """Get company info with multi-provider fallback."""
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"info:{normalized}"

        cached = self._get_cache(cache_key)
        if cached:
            return CompanyInfo(**cached)

        # Try yfinance first
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

        # Try Finnhub
        fh_profile = await self.multi_provider.finnhub.get_company_profile(normalized)
        if fh_profile:
            result = CompanyInfo(
                symbol=normalized,
                name=fh_profile.get("name", normalized),
                sector=fh_profile.get("finnhubIndustry"),
                industry=fh_profile.get("finnhubIndustry"),
                market_cap=fh_profile.get("marketCapitalization"),
                description=(fh_profile.get("description") or "")[:300],
                source="finnhub",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(by_alias=True), settings.CACHE_TTL_INFO)
            return result

        # Try Alpha Vantage
        av_overview = await self.multi_provider.alpha_vantage.get_company_overview(normalized)
        if av_overview:
            market_cap = av_overview.get("MarketCapitalization")
            pe_ratio = av_overview.get("PERatio")
            result = CompanyInfo(
                symbol=normalized,
                name=av_overview.get("Name") or normalized,
                sector=av_overview.get("Sector"),
                industry=av_overview.get("Industry"),
                market_cap=int(market_cap) if market_cap and market_cap.isdigit() else None,
                pe_ratio=float(pe_ratio) if pe_ratio and pe_ratio not in {"None", "-"} else None,
                week_52_high=float(av_overview["52WeekHigh"]) if av_overview.get("52WeekHigh") not in {None, "None", "-"} else None,
                week_52_low=float(av_overview["52WeekLow"]) if av_overview.get("52WeekLow") not in {None, "None", "-"} else None,
                description=(av_overview.get("Description") or "")[:300],
                source="alpha_vantage",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(by_alias=True), settings.CACHE_TTL_INFO)
            return result

        # Try FMP
        fmp_profile = await self.multi_provider.fmp.get_profile(normalized)
        if fmp_profile:
            result = CompanyInfo(
                symbol=normalized,
                name=fmp_profile.get("companyName", normalized),
                sector=fmp_profile.get("sector"),
                industry=fmp_profile.get("industry"),
                market_cap=fmp_profile.get("mktCap"),
                description=(fmp_profile.get("description") or "")[:300],
                source="fmp",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(by_alias=True), settings.CACHE_TTL_INFO)
            return result

        return CompanyInfo(
            symbol=normalized,
            name=normalized or symbol,
            source="unavailable",
            timestamp=self._utc_now(),
        )

    async def get_economic_indicator(self, series_id: str) -> Optional[Any]:
        """Get economic indicator from FRED."""
        cache_key = f"fred:{series_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        data = await self.multi_provider.get_economic_data(series_id)
        if data is not None:
            # Convert pandas Series to dict for caching
            result = {"series_id": series_id, "data": data.to_dict(), "timestamp": self._utc_now()}
            self._set_cache(cache_key, result, 86400)  # Cache for 24 hours
            return result

        return None

    async def get_forex_rate(self, base: str, target: str) -> Optional[Dict[str, Any]]:
        """Get forex rate from Frankfurter."""
        cache_key = f"forex:{base}:{target}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        data = await self.multi_provider.get_forex_rate(base, target)
        if data:
            self._set_cache(cache_key, data, settings.CACHE_TTL_PRICE)
            return data

        return None

    def check_cache(self) -> bool:
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False
