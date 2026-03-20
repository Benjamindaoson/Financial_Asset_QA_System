"""
Test suite for multi-provider financial API integration.
"""

import pytest
from app.market.api_providers import (
    AlphaVantageProvider,
    FinnhubProvider,
    FREDProvider,
    PolygonProvider,
    TwelveDataProvider,
    FMPProvider,
    CoinGeckoProvider,
    FrankfurterProvider,
    MultiProviderClient,
)
from app.market.enhanced_service import EnhancedMarketDataService


@pytest.mark.asyncio
class TestAlphaVantageProvider:
    """Test Alpha Vantage API provider."""

    async def test_get_quote(self):
        provider = AlphaVantageProvider()
        result = await provider.get_quote("AAPL")
        if result:
            assert "05. price" in result
            assert float(result["05. price"]) > 0

    async def test_get_company_overview(self):
        provider = AlphaVantageProvider()
        result = await provider.get_company_overview("AAPL")
        if result:
            assert result.get("Symbol") == "AAPL"
            assert "Name" in result


@pytest.mark.asyncio
class TestFinnhubProvider:
    """Test Finnhub API provider."""

    async def test_get_quote(self):
        provider = FinnhubProvider()
        result = await provider.get_quote("AAPL")
        if result:
            assert "c" in result  # current price
            assert result["c"] > 0

    async def test_get_company_profile(self):
        provider = FinnhubProvider()
        result = await provider.get_company_profile("AAPL")
        if result:
            assert "name" in result
            assert "ticker" in result

    async def test_get_news(self):
        provider = FinnhubProvider()
        result = await provider.get_news("AAPL", "2024-01-01", "2024-01-31")
        if result:
            assert isinstance(result, list)
            if result:
                assert "headline" in result[0]


@pytest.mark.asyncio
class TestFREDProvider:
    """Test FRED API provider."""

    async def test_get_series(self):
        provider = FREDProvider()
        result = await provider.get_series("GDP")
        if result is not None:
            assert len(result) > 0

    async def test_get_series_info(self):
        provider = FREDProvider()
        result = await provider.get_series_info("GDP")
        if result:
            assert "id" in result
            assert result["id"] == "GDP"


@pytest.mark.asyncio
class TestPolygonProvider:
    """Test Polygon.io API provider."""

    async def test_get_previous_close(self):
        provider = PolygonProvider()
        result = await provider.get_previous_close("AAPL")
        if result:
            assert "c" in result  # close price
            assert result["c"] > 0

    async def test_get_ticker_details(self):
        provider = PolygonProvider()
        result = await provider.get_ticker_details("AAPL")
        if result:
            assert "ticker" in result
            assert result["ticker"] == "AAPL"


@pytest.mark.asyncio
class TestTwelveDataProvider:
    """Test Twelve Data API provider."""

    async def test_get_quote(self):
        provider = TwelveDataProvider()
        result = await provider.get_quote("AAPL")
        if result:
            assert "close" in result or "price" in result

    async def test_get_time_series(self):
        provider = TwelveDataProvider()
        result = await provider.get_time_series("AAPL", interval="1day", outputsize=5)
        if result:
            assert "values" in result or "data" in result


@pytest.mark.asyncio
class TestFMPProvider:
    """Test Financial Modeling Prep API provider."""

    async def test_get_quote(self):
        provider = FMPProvider()
        result = await provider.get_quote("AAPL")
        if result:
            assert "price" in result
            assert result["price"] > 0

    async def test_get_profile(self):
        provider = FMPProvider()
        result = await provider.get_profile("AAPL")
        if result:
            assert "companyName" in result
            assert "symbol" in result

    async def test_get_income_statement(self):
        provider = FMPProvider()
        result = await provider.get_income_statement("AAPL", period="annual", limit=1)
        if result:
            assert isinstance(result, list)
            if result:
                assert "revenue" in result[0]


@pytest.mark.asyncio
class TestCoinGeckoProvider:
    """Test CoinGecko API provider (no API key required)."""

    async def test_get_price(self):
        provider = CoinGeckoProvider()
        result = await provider.get_price("bitcoin")
        assert result is not None
        assert "usd" in result
        assert result["usd"] > 0

    async def test_get_coin_info(self):
        provider = CoinGeckoProvider()
        result = await provider.get_coin_info("bitcoin")
        assert result is not None
        assert "id" in result
        assert result["id"] == "bitcoin"


@pytest.mark.asyncio
class TestFrankfurterProvider:
    """Test Frankfurter API provider (no API key required)."""

    async def test_get_latest_rates(self):
        provider = FrankfurterProvider()
        result = await provider.get_latest_rates("USD", "EUR")
        assert result is not None
        assert "rates" in result
        assert "EUR" in result["rates"]
        assert result["rates"]["EUR"] > 0

    async def test_get_historical_rates(self):
        provider = FrankfurterProvider()
        result = await provider.get_historical_rates("2024-01-01", "USD", "EUR")
        assert result is not None
        assert "rates" in result
        assert "EUR" in result["rates"]


@pytest.mark.asyncio
class TestMultiProviderClient:
    """Test multi-provider client."""

    async def test_get_stock_quote_multi(self):
        client = MultiProviderClient()
        results = await client.get_stock_quote_multi("AAPL")
        assert isinstance(results, dict)
        # At least one provider should return data
        assert len(results) > 0

    async def test_get_crypto_price(self):
        client = MultiProviderClient()
        result = await client.get_crypto_price("bitcoin")
        assert result is not None
        assert "usd" in result

    async def test_get_forex_rate(self):
        client = MultiProviderClient()
        result = await client.get_forex_rate("USD", "EUR")
        assert result is not None
        assert "rates" in result

    async def test_get_economic_data(self):
        client = MultiProviderClient()
        result = await client.get_economic_data("GDP")
        # May be None if FRED API key not configured
        if result is not None:
            assert len(result) > 0


@pytest.mark.asyncio
class TestEnhancedMarketDataService:
    """Test enhanced market data service."""

    async def test_get_price_stock(self):
        service = EnhancedMarketDataService()
        result = await service.get_price("AAPL")
        assert result.symbol == "AAPL"
        if result.price:
            assert result.price > 0
            assert result.source in ["yfinance", "finnhub", "alpha_vantage", "twelve_data", "fmp", "polygon"]

    async def test_get_price_crypto(self):
        service = EnhancedMarketDataService()
        result = await service.get_price("BTC-USD")
        assert result.symbol == "BTC-USD"
        if result.price:
            assert result.price > 0

    async def test_get_history(self):
        service = EnhancedMarketDataService()
        result = await service.get_history("AAPL", days=7)
        assert result.symbol == "AAPL"
        assert result.days == 7
        if result.data:
            assert len(result.data) > 0
            assert result.data[0].close > 0

    async def test_get_change(self):
        service = EnhancedMarketDataService()
        result = await service.get_change("AAPL", days=7)
        assert result.symbol == "AAPL"
        assert result.days == 7
        assert result.trend in ["上涨", "下跌", "震荡"]

    async def test_get_info(self):
        service = EnhancedMarketDataService()
        result = await service.get_info("AAPL")
        assert result.symbol == "AAPL"
        if result.name:
            assert len(result.name) > 0

    async def test_get_forex_rate(self):
        service = EnhancedMarketDataService()
        result = await service.get_forex_rate("USD", "EUR")
        assert result is not None
        assert "rates" in result

    async def test_cache_functionality(self):
        service = EnhancedMarketDataService()

        # First call - should not be cached
        result1 = await service.get_price("AAPL")
        assert result1.cache_hit is False

        # Second call - should be cached
        result2 = await service.get_price("AAPL")
        if service.check_cache():
            assert result2.cache_hit is True
            assert result2.price == result1.price


@pytest.mark.asyncio
class TestTickerMapper:
    """Test ticker symbol mapping."""

    def test_normalize_chinese_names(self):
        from app.market.enhanced_service import TickerMapper

        assert TickerMapper.normalize("苹果") == "AAPL"
        assert TickerMapper.normalize("特斯拉") == "TSLA"
        assert TickerMapper.normalize("茅台") == "600519.SS"

    def test_normalize_chinese_stock_codes(self):
        from app.market.enhanced_service import TickerMapper

        assert TickerMapper.normalize("600519") == "600519.SS"  # Shanghai
        assert TickerMapper.normalize("000001") == "000001.SZ"  # Shenzhen
        assert TickerMapper.normalize("300750") == "300750.SZ"  # ChiNext

    def test_is_crypto(self):
        from app.market.enhanced_service import TickerMapper

        assert TickerMapper.is_crypto("BTC-USD") is True
        assert TickerMapper.is_crypto("ETH-USD") is True
        assert TickerMapper.is_crypto("AAPL") is False

    def test_get_crypto_id(self):
        from app.market.enhanced_service import TickerMapper

        assert TickerMapper.get_crypto_id("BTC-USD") == "bitcoin"
        assert TickerMapper.get_crypto_id("ETH-USD") == "ethereum"


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for complete workflows."""

    async def test_multi_asset_portfolio(self):
        """Test fetching data for a multi-asset portfolio."""
        service = EnhancedMarketDataService()

        assets = {
            "stocks": ["AAPL", "GOOGL"],
            "crypto": ["BTC-USD"],
        }

        results = {}

        # Fetch stock prices
        for symbol in assets["stocks"]:
            results[symbol] = await service.get_price(symbol)
            assert results[symbol].symbol == symbol

        # Fetch crypto prices
        for symbol in assets["crypto"]:
            results[symbol] = await service.get_price(symbol)
            assert results[symbol].symbol == symbol

    async def test_economic_dashboard(self):
        """Test fetching economic indicators."""
        service = EnhancedMarketDataService()

        indicators = ["GDP", "UNRATE", "CPIAUCSL"]
        results = {}

        for indicator in indicators:
            data = await service.get_economic_indicator(indicator)
            if data:
                results[indicator] = data
                assert "series_id" in data
                assert data["series_id"] == indicator

    async def test_forex_conversion(self):
        """Test forex rate conversion."""
        service = EnhancedMarketDataService()

        # Get multiple forex rates
        pairs = [("USD", "EUR"), ("USD", "GBP"), ("USD", "JPY")]

        for base, target in pairs:
            rate = await service.get_forex_rate(base, target)
            if rate:
                assert "rates" in rate
                assert target in rate["rates"]
                assert rate["rates"][target] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
