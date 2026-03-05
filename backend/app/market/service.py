"""
Market Data Service - handles stock price data with dual-source fallback
"""
import yfinance as yf
import redis
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from app.config import settings
from app.models import MarketData, HistoryData, ChangeData, CompanyInfo, PricePoint


class TickerMapper:
    """Maps company names and aliases to ticker symbols"""

    # Exact mapping for common stocks
    EXACT_MAP = {
        "阿里巴巴": "BABA",
        "腾讯": "0700.HK",
        "茅台": "600519.SS",
        "贵州茅台": "600519.SS",
        "苹果": "AAPL",
        "特斯拉": "TSLA",
        "比特币": "BTC-USD",
        "以太坊": "ETH-USD",
    }

    @classmethod
    def normalize(cls, symbol: str) -> str:
        """
        Three-level normalization:
        1. Exact mapping lookup
        2. A-share format conversion (6-digit -> XXXXXX.SS/SZ)
        3. Pass-through
        """
        # Level 1: Exact mapping
        if symbol in cls.EXACT_MAP:
            return cls.EXACT_MAP[symbol]

        # Level 2: A-share format
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith('6'):
                return f"{symbol}.SS"  # Shanghai
            elif symbol.startswith(('0', '3')):
                return f"{symbol}.SZ"  # Shenzhen

        # Level 3: Pass-through
        return symbol.upper()


class MarketDataService:
    """Market data service with Redis caching and dual-source fallback"""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.ticker_mapper = TickerMapper()

    def _get_cache(self, key: str) -> Optional[dict]:
        """Get data from Redis cache"""
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    def _set_cache(self, key: str, value: dict, ttl: int):
        """Set data to Redis cache with TTL"""
        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    async def _fetch_yfinance(self, symbol: str) -> Optional[yf.Ticker]:
        """Fetch data from yfinance (async wrapper)"""
        try:
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            return ticker
        except Exception:
            return None

    async def get_price(self, symbol: str) -> MarketData:
        """
        Get current price for a symbol
        Cache: 60 seconds
        """
        # Normalize symbol
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"price:{normalized}"

        # Check cache
        cached = self._get_cache(cache_key)
        if cached:
            return MarketData(**cached)

        # Fetch from yfinance
        ticker = await self._fetch_yfinance(normalized)
        if ticker:
            try:
                info = await asyncio.to_thread(lambda: ticker.info)
                price = info.get('currentPrice') or info.get('regularMarketPrice')

                if price:
                    result = MarketData(
                        symbol=normalized,
                        price=price,
                        currency=info.get('currency', 'USD'),
                        name=info.get('longName', normalized),
                        source="yfinance",
                        timestamp=datetime.utcnow().isoformat()
                    )

                    # Cache result
                    self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_PRICE)
                    return result
            except Exception:
                pass

        # Fallback to Alpha Vantage (if configured)
        if settings.ALPHA_VANTAGE_API_KEY:
            result = await self._fetch_alpha_vantage(normalized)
            if result:
                self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_PRICE)
                return result

        # Return error
        return MarketData(
            symbol=normalized,
            source="unavailable",
            timestamp=datetime.utcnow().isoformat(),
            error="Data unavailable from all sources"
        )

    async def _fetch_alpha_vantage(self, symbol: str) -> Optional[MarketData]:
        """Fetch from Alpha Vantage API (fallback)"""
        # Stub implementation - would call Alpha Vantage API
        return None

    async def get_history(self, symbol: str, days: int = 30) -> HistoryData:
        """
        Get historical price data
        Cache: 24 hours
        """
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"history:{normalized}:{days}"

        # Check cache
        cached = self._get_cache(cache_key)
        if cached:
            return HistoryData(**cached)

        # Fetch from yfinance
        ticker = await self._fetch_yfinance(normalized)
        if ticker:
            try:
                hist = await asyncio.to_thread(
                    lambda: ticker.history(period=f"{days}d")
                )

                if not hist.empty:
                    data = [
                        PricePoint(
                            date=idx.strftime('%Y-%m-%d'),
                            open=row['Open'],
                            high=row['High'],
                            low=row['Low'],
                            close=row['Close'],
                            volume=int(row['Volume'])
                        )
                        for idx, row in hist.iterrows()
                    ]

                    result = HistoryData(
                        symbol=normalized,
                        days=days,
                        data=data,
                        source="yfinance",
                        timestamp=datetime.utcnow().isoformat()
                    )

                    self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_HISTORY)
                    return result
            except Exception:
                pass

        # Return empty result
        return HistoryData(
            symbol=normalized,
            days=days,
            data=[],
            source="unavailable",
            timestamp=datetime.utcnow().isoformat()
        )

    async def get_change(self, symbol: str, days: int = 7) -> ChangeData:
        """
        Calculate price change over period
        Cache: 60 seconds
        """
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"change:{normalized}:{days}"

        # Check cache
        cached = self._get_cache(cache_key)
        if cached:
            return ChangeData(**cached)

        # Get historical data
        history = await self.get_history(normalized, days)

        if len(history.data) >= 2:
            start_price = history.data[0].close
            end_price = history.data[-1].close
            change_pct = ((end_price - start_price) / start_price) * 100

            # Determine trend
            if change_pct > 2:
                trend = "上涨"
            elif change_pct < -2:
                trend = "下跌"
            else:
                trend = "震荡"

            result = ChangeData(
                symbol=normalized,
                days=days,
                start_price=start_price,
                end_price=end_price,
                change_pct=round(change_pct, 2),
                trend=trend,
                source=history.source,
                timestamp=datetime.utcnow().isoformat()
            )

            self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_PRICE)
            return result

        # Return default
        return ChangeData(
            symbol=normalized,
            days=days,
            start_price=0,
            end_price=0,
            change_pct=0,
            trend="震荡",
            source="unavailable",
            timestamp=datetime.utcnow().isoformat()
        )

    async def get_info(self, symbol: str) -> CompanyInfo:
        """
        Get company information
        Cache: 7 days
        """
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"info:{normalized}"

        # Check cache
        cached = self._get_cache(cache_key)
        if cached:
            return CompanyInfo(**cached)

        # Fetch from yfinance
        ticker = await self._fetch_yfinance(normalized)
        if ticker:
            try:
                info = await asyncio.to_thread(lambda: ticker.info)

                result = CompanyInfo(
                    symbol=normalized,
                    name=info.get('longName', normalized),
                    sector=info.get('sector'),
                    industry=info.get('industry'),
                    market_cap=info.get('marketCap'),
                    pe_ratio=info.get('trailingPE'),
                    week_52_high=info.get('fiftyTwoWeekHigh'),
                    week_52_low=info.get('fiftyTwoWeekLow'),
                    description=info.get('longBusinessSummary', '')[:300],
                    source="yfinance",
                    timestamp=datetime.utcnow().isoformat()
                )

                self._set_cache(cache_key, result.model_dump(), settings.CACHE_TTL_INFO)
                return result
            except Exception:
                pass

        # Return minimal info
        return CompanyInfo(
            symbol=normalized,
            name=normalized,
            source="unavailable",
            timestamp=datetime.utcnow().isoformat()
        )
