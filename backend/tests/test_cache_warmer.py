import pytest
from app.cache.warmer import CacheWarmer
from app.market import MarketDataService

@pytest.mark.asyncio
async def test_cache_warmer_preloads_popular_stocks():
    """Test that cache warmer preloads TOP stocks."""
    service = MarketDataService()
    warmer = CacheWarmer(market_service=service)

    # Warm cache for top 3 stocks
    await warmer.warm_popular_stocks(limit=3)

    # Verify cache hit - use the same service instance
    result = await service.get_price("AAPL")

    assert result.cache_hit is True
    assert result.latency_ms < 100  # Should be fast from cache
