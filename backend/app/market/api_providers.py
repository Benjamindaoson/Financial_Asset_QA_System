"""
Multi-provider financial data API integration.
Supports: Alpha Vantage, Finnhub, FRED, Polygon, Twelve Data, FMP, CoinGecko, Frankfurter, NewsAPI
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fredapi import Fred

from app.config import settings


class AlphaVantageProvider:
    """Alpha Vantage API provider - 25 requests/day free."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ALPHA_VANTAGE_API_KEY

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.BASE_URL, params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                if "Error Message" in data or "Note" in data:
                    return None
                return data.get("Global Quote")
        except Exception:
            return None

    async def get_daily_history(self, symbol: str, outputsize: str = "compact") -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.BASE_URL, params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                return data.get("Time Series (Daily)")
        except Exception:
            return None

    async def get_company_overview(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.BASE_URL, params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                if not data.get("Symbol"):
                    return None
                return data
        except Exception:
            return None


class FinnhubProvider:
    """Finnhub API provider - 60 requests/minute free."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FINNHUB_API_KEY

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/quote",
                    params={"symbol": symbol, "token": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if data.get("c") == 0:  # No data
                    return None
                return data
        except Exception:
            return None

    async def get_candles(self, symbol: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Fetch historical candle data. Returns dict with c, h, l, o, v, t, s keys."""
        if not self.api_key:
            return None

        import time
        now = int(time.time())
        from_ts = now - days * 86400

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/stock/candle",
                    params={
                        "symbol": symbol,
                        "resolution": "D",
                        "from": from_ts,
                        "to": now,
                        "token": self.api_key,
                    }
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if data.get("s") != "ok":
                    return None
                return data
        except Exception:
            return None

    async def get_company_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/stock/profile2",
                    params={"symbol": symbol, "token": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if not data:
                    return None
                return data
        except Exception:
            return None

    async def get_news(self, symbol: str, from_date: str = None, to_date: str = None) -> Optional[List[Dict[str, Any]]]:
        if not self.api_key:
            return None

        params = {"symbol": symbol, "token": self.api_key}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.BASE_URL}/company-news", params=params)
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None


class FREDProvider:
    """FRED (Federal Reserve Economic Data) - Unlimited free access."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FRED_API_KEY
        self.fred = Fred(api_key=self.api_key) if self.api_key else None

    async def get_series(self, series_id: str) -> Optional[Any]:
        """Get economic data series (e.g., GDP, unemployment rate)."""
        if not self.fred:
            return None

        try:
            return await asyncio.to_thread(self.fred.get_series, series_id)
        except Exception:
            return None

    async def get_series_info(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata about a series."""
        if not self.fred:
            return None

        try:
            return await asyncio.to_thread(self.fred.get_series_info, series_id)
        except Exception:
            return None


class PolygonProvider:
    """Polygon.io API provider - 5 requests/minute free (15-min delayed)."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.POLYGON_API_KEY

    async def get_previous_close(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/v2/aggs/ticker/{symbol}/prev",
                    params={"apiKey": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if data.get("status") != "OK":
                    return None
                return data.get("results", [{}])[0] if data.get("results") else None
        except Exception:
            return None

    async def get_ticker_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/v3/reference/tickers/{symbol}",
                    params={"apiKey": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                return data.get("results")
        except Exception:
            return None


class TwelveDataProvider:
    """Twelve Data API provider - Limited daily credits free."""

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.TWELVE_DATA_API_KEY

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/quote",
                    params={"symbol": symbol, "apikey": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if "code" in data:  # Error response
                    return None
                return data
        except Exception:
            return None

    async def get_time_series(self, symbol: str, interval: str = "1day", outputsize: int = 30) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/time_series",
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "outputsize": outputsize,
                        "apikey": self.api_key
                    }
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if "code" in data:
                    return None
                return data
        except Exception:
            return None


class FMPProvider:
    """Financial Modeling Prep API provider."""

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FMP_API_KEY

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/quote/{symbol}",
                    params={"apikey": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if not data or isinstance(data, dict) and "Error Message" in data:
                    return None
                return data[0] if isinstance(data, list) and data else None
        except Exception:
            return None

    async def get_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/profile/{symbol}",
                    params={"apikey": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if not data or isinstance(data, dict) and "Error Message" in data:
                    return None
                return data[0] if isinstance(data, list) and data else None
        except Exception:
            return None

    async def get_income_statement(self, symbol: str, period: str = "annual", limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/income-statement/{symbol}",
                    params={"period": period, "limit": limit, "apikey": self.api_key}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if isinstance(data, dict) and "Error Message" in data:
                    return None
                return data
        except Exception:
            return None


class CoinGeckoProvider:
    """CoinGecko API provider - Free, no API key required."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    async def get_price(self, coin_id: str, vs_currency: str = "usd") -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.BASE_URL}/simple/price",
                    params={
                        "ids": coin_id,
                        "vs_currencies": vs_currency,
                        "include_24hr_change": "true",
                        "include_market_cap": "true"
                    }
                )
                if response.status_code != 200:
                    return None
                return response.json().get(coin_id)
        except Exception:
            return None

    async def get_coin_info(self, coin_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.BASE_URL}/coins/{coin_id}")
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None


class FrankfurterProvider:
    """Frankfurter API provider - Free forex rates, no API key required."""

    BASE_URL = "https://api.frankfurter.app"

    async def get_latest_rates(self, base: str = "USD", symbols: Optional[str] = None) -> Optional[Dict[str, Any]]:
        params = {"from": base}
        if symbols:
            params["to"] = symbols

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.BASE_URL}/latest", params=params)
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None

    async def get_historical_rates(self, date: str, base: str = "USD", symbols: Optional[str] = None) -> Optional[Dict[str, Any]]:
        params = {"from": base}
        if symbols:
            params["to"] = symbols

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.BASE_URL}/{date}", params=params)
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None


class NewsAPIProvider:
    """NewsAPI.org provider - 100 requests/day free."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.NEWSAPI_API_KEY

    async def get_everything(
        self,
        query: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        page_size: int = 20
    ) -> Optional[Dict[str, Any]]:
        """Search for news articles."""
        if not self.api_key:
            return None

        params = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": page_size,
            "apiKey": self.api_key
        }

        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{self.BASE_URL}/everything", params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                if data.get("status") != "ok":
                    return None
                return data
        except Exception:
            return None

    async def get_top_headlines(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        page_size: int = 20
    ) -> Optional[Dict[str, Any]]:
        """Get top headlines."""
        if not self.api_key:
            return None

        params = {
            "pageSize": page_size,
            "apiKey": self.api_key
        }

        if country:
            params["country"] = country
        if category:
            params["category"] = category
        if query:
            params["q"] = query

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{self.BASE_URL}/top-headlines", params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                if data.get("status") != "ok":
                    return None
                return data
        except Exception:
            return None

    async def get_stock_news(self, symbol: str, days: int = 7, page_size: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Get news for a specific stock symbol."""
        if not self.api_key:
            return None

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        # Search for company name or symbol
        result = await self.get_everything(
            query=symbol,
            from_date=from_str,
            to_date=to_str,
            sort_by="publishedAt",
            page_size=page_size
        )

        if not result or "articles" not in result:
            return None

        # Format articles
        articles = []
        for article in result["articles"]:
            articles.append({
                "title": article.get("title"),
                "description": article.get("description"),
                "url": article.get("url"),
                "source": article.get("source", {}).get("name"),
                "published_at": article.get("publishedAt"),
                "author": article.get("author"),
                "image_url": article.get("urlToImage")
            })

        return articles


class MultiProviderClient:
    """Unified client for all financial data providers."""

    def __init__(self):
        self.alpha_vantage = AlphaVantageProvider()
        self.finnhub = FinnhubProvider()
        self.fred = FREDProvider()
        self.polygon = PolygonProvider()
        self.twelve_data = TwelveDataProvider()
        self.fmp = FMPProvider()
        self.coingecko = CoinGeckoProvider()
        self.frankfurter = FrankfurterProvider()
        self.newsapi = NewsAPIProvider()

    async def get_stock_quote_multi(self, symbol: str) -> Dict[str, Any]:
        """Try multiple providers for stock quote."""
        results = {}

        # Try all providers in parallel
        tasks = {
            "finnhub": self.finnhub.get_quote(symbol),
            "alpha_vantage": self.alpha_vantage.get_quote(symbol),
            "twelve_data": self.twelve_data.get_quote(symbol),
            "fmp": self.fmp.get_quote(symbol),
            "polygon": self.polygon.get_previous_close(symbol),
        }

        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for provider, response in zip(tasks.keys(), responses):
            if response and not isinstance(response, Exception):
                results[provider] = response

        return results

    async def get_crypto_price(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """Get cryptocurrency price from CoinGecko."""
        return await self.coingecko.get_price(coin_id)

    async def get_forex_rate(self, base: str, target: str) -> Optional[Dict[str, Any]]:
        """Get forex rate from Frankfurter."""
        return await self.frankfurter.get_latest_rates(base, target)

    async def get_economic_data(self, series_id: str) -> Optional[Any]:
        """Get economic indicator from FRED."""
        return await self.fred.get_series(series_id)

    async def get_stock_news(self, symbol: str, days: int = 7) -> Optional[List[Dict[str, Any]]]:
        """Get news for a stock from NewsAPI."""
        return await self.newsapi.get_stock_news(symbol, days=days)
