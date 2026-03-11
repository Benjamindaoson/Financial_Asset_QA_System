import pytest
from unittest.mock import AsyncMock, patch
from app.cache.warmer import CacheWarmer
from app.market import MarketDataService
from app.models import MarketData

@pytest.mark.asyncio
async def test_cache_warmer_preloads_popular_stocks():
    """Test that cache warmer preloads TOP stocks."""
    service = MarketDataService()
    warmer = CacheWarmer(market_service=service)

    # Mock the market service methods to avoid API rate limits
    mock_price_data = MarketData(
        symbol="AAPL",
        price=180.0,
        currency="USD",
        name="Apple Inc.",
        source="mock",
        timestamp="2026-03-07T15:00:00",
        cache_hit=False,
        latency_ms=50.0
    )

    with patch.object(service, 'get_price', new_callable=AsyncMock) as mock_get_price, \
         patch.object(service, 'get_history', new_callable=AsyncMock) as mock_get_history:

        mock_get_price.return_value = mock_price_data
        mock_get_history.return_value = AsyncMock()

        # Warm cache for top 3 stocks
        await warmer.warm_popular_stocks(limit=3)

        # Verify that get_price and get_history were called for each stock
        assert mock_get_price.call_count == 3
        assert mock_get_history.call_count == 3

@pytest.mark.asyncio
async def test_cache_warmer_with_real_cache():
    """Test cache-backed price reads without calling external providers."""
    service = MarketDataService()

    test_data = {
        "symbol": "AAPL",
        "price": 180.0,
        "currency": "USD",
        "name": "Apple Inc.",
        "source": "test",
        "timestamp": "2026-03-07T15:00:00",
        "error": None,
    }

    with patch.object(service, "_get_cache", return_value=test_data), \
         patch.object(service.finnhub_provider, "get_quote", new_callable=AsyncMock) as mock_get_quote:
        result = await service.get_price("AAPL")

    assert result.cache_hit is True
    assert result.latency_ms < 100
    assert result.price == 180.0
    mock_get_quote.assert_not_called()
