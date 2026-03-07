"""Cache warmer for preloading popular stock data."""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.cache.popular_stocks import get_popular_stocks
from app.market import MarketDataService

logger = logging.getLogger(__name__)


class CacheWarmer:
    """Preloads popular stock data into Redis cache."""

    def __init__(
        self,
        market_service: MarketDataService,
        interval_seconds: int = 30,
    ):
        self.market_service = market_service
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None

    async def warm_popular_stocks(self, limit: int = 100):
        """Warm cache for top N popular stocks."""
        stocks = get_popular_stocks(limit)

        logger.info(f"[CacheWarmer] Warming {len(stocks)} popular stocks...")
        start_time = datetime.now()

        # Parallel fetch with concurrency limit
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        async def fetch_with_limit(symbol: str):
            async with semaphore:
                try:
                    await self.market_service.get_price(symbol)
                    await self.market_service.get_history(symbol, days=30)
                except Exception as e:
                    logger.warning(f"[CacheWarmer] Failed to warm {symbol}: {e}")

        await asyncio.gather(*[fetch_with_limit(s) for s in stocks])

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[CacheWarmer] Completed in {elapsed:.2f}s")

    async def start_background_warming(self):
        """Start background task that warms cache periodically."""
        if self._task is not None and not self._task.done():
            logger.warning("[CacheWarmer] Background warming already running")
            return

        async def warming_loop():
            while True:
                try:
                    await self.warm_popular_stocks()
                    await asyncio.sleep(self.interval_seconds)
                except Exception as e:
                    logger.error(f"[CacheWarmer] Error in warming loop: {e}")
                    await asyncio.sleep(60)  # Retry after 1 minute

        self._task = asyncio.create_task(warming_loop())
        logger.info(f"[CacheWarmer] Background warming started (interval={self.interval_seconds}s)")

    async def stop(self):
        """Stop background warming task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None
