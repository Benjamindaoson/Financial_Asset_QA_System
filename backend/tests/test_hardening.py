"""Hardening tests for fallback behavior and grounded response validation."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agent.core import ResponseGuard
from app.market.service import MarketDataService
from app.models.schemas import HistoryData, MarketData, PricePoint, ToolResult


class TestMarketFallback:
    @pytest.fixture
    def service(self):
        with patch("app.market.service.redis.Redis"):
            return MarketDataService()

    @pytest.mark.asyncio
    async def test_get_price_uses_alpha_vantage_fallback(self, service):
        service._get_cache = Mock(return_value=None)
        service._fetch_yfinance_info = AsyncMock(return_value=None)
        service._fetch_alpha_vantage_quote = AsyncMock(
            return_value=MarketData(
                symbol="AAPL",
                price=150.0,
                currency="USD",
                name="Apple Inc.",
                source="alpha_vantage",
                timestamp="2026-03-06T00:00:00",
            )
        )

        result = await service.get_price("AAPL")

        assert result.source == "alpha_vantage"
        assert result.price == 150.0

    @pytest.mark.asyncio
    async def test_get_history_uses_alpha_vantage_fallback(self, service):
        service._get_cache = Mock(return_value=None)
        service._fetch_yfinance_history = AsyncMock(return_value=None)
        service._fetch_alpha_vantage_history = AsyncMock(
            return_value=HistoryData(
                symbol="AAPL",
                days=7,
                data=[
                    PricePoint(date="2026-03-01", open=100, high=101, low=99, close=100, volume=1),
                    PricePoint(date="2026-03-02", open=101, high=102, low=100, close=101, volume=1),
                ],
                source="alpha_vantage",
                timestamp="2026-03-06T00:00:00",
            )
        )

        result = await service.get_history("AAPL", 7)

        assert result.source == "alpha_vantage"
        assert len(result.data) == 2


class TestResponseGuardHardening:
    def test_validate_rejects_unsupported_number(self):
        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    "symbol": "AAPL",
                    "price": 150.0,
                    "currency": "USD",
                    "source": "yfinance",
                    "timestamp": "2026-03-06T00:00:00",
                },
                latency_ms=10,
                status="success",
                data_source="yfinance",
                cache_hit=False,
                error_message=None,
            )
        ]

        response = """## Data Summary
- AAPL is trading at 151.00 USD

## Analysis
- The answer is grounded.

## Sources
- yfinance

## Uncertainty
- No additional uncertainty."""

        assert ResponseGuard.validate(response, tool_results) is False

    def test_validate_accepts_grounded_answer(self):
        tool_results = [
            ToolResult(
                tool="get_change",
                data={
                    "symbol": "AAPL",
                    "days": 7,
                    "change_pct": 3.45,
                    "source": "yfinance",
                    "timestamp": "2026-03-06T00:00:00",
                },
                latency_ms=10,
                status="success",
                data_source="yfinance",
                cache_hit=False,
                error_message=None,
            )
        ]

        response = """## Data Summary
- AAPL changed 3.45% over 7 days.

## Analysis
- The move is summarized from verified market data.

## Sources
- yfinance

## Uncertainty
- No additional uncertainty."""

        assert ResponseGuard.validate(response, tool_results) is True
