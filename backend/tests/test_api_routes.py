"""Tests for API routes."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes import router
from app.models.schemas import PricePoint, SSEEvent


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router, prefix="/api")
    return application


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


class TestHealthEndpoint:
    @patch("app.api.routes.market_service")
    @patch("app.api.routes.agent")
    @patch("app.api.routes.settings")
    @pytest.mark.asyncio
    async def test_health_all_healthy(self, mock_settings, mock_agent, mock_market, client):
        mock_market.redis_client.ping.return_value = True
        mock_agent.rag_pipeline.get_collection_count.return_value = 100
        mock_settings.DEEPSEEK_API_KEY = "test-key"
        mock_settings.ALPHA_VANTAGE_API_KEY = None
        mock_settings.TAVILY_API_KEY = None

        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["components"]["redis"] == "connected"
        assert data["components"]["deepseek_api"] == "configured"

    @patch("app.api.routes.market_service")
    @patch("app.api.routes.agent")
    @patch("app.api.routes.settings")
    @pytest.mark.asyncio
    async def test_health_redis_down(self, mock_settings, mock_agent, mock_market, client):
        mock_market.redis_client.ping.side_effect = Exception("Connection failed")
        mock_agent.rag_pipeline.get_collection_count.return_value = 100
        mock_settings.DEEPSEEK_API_KEY = "test-key"
        mock_settings.ALPHA_VANTAGE_API_KEY = None
        mock_settings.TAVILY_API_KEY = None

        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"] == "disconnected"

    @patch("app.api.routes.market_service")
    @patch("app.api.routes.agent")
    @patch("app.api.routes.settings")
    @pytest.mark.asyncio
    async def test_health_no_api_key(self, mock_settings, mock_agent, mock_market, client):
        mock_market.redis_client.ping.return_value = True
        mock_agent.rag_pipeline.get_collection_count.return_value = 100
        mock_settings.DEEPSEEK_API_KEY = ""
        mock_settings.ALPHA_VANTAGE_API_KEY = None
        mock_settings.TAVILY_API_KEY = None

        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["deepseek_api"] == "not_configured"


class TestModelsEndpoint:
    @patch("app.api.routes.agent")
    @pytest.mark.asyncio
    async def test_list_models(self, mock_agent, client):
        mock_agent.get_available_models.return_value = [{"name": "deepseek-chat", "provider": "deepseek"}]
        mock_agent.get_usage_report.return_value = {"total_requests": 100, "total_tokens": 50000}

        response = await client.get("/api/models")

        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "deepseek-chat"


class TestChartEndpoint:
    @patch("app.api.routes.market_service")
    @pytest.mark.asyncio
    async def test_get_chart_success(self, mock_market, client):
        from app.models.schemas import HistoryData

        mock_history = HistoryData(
            symbol="AAPL",
            days=30,
            data=[
                PricePoint(
                    date="2024-03-01",
                    open=150.0,
                    high=152.0,
                    low=148.0,
                    close=151.0,
                    volume=1000000,
                )
            ],
            source="yfinance",
            timestamp="2024-03-05T10:00:00",
        )
        mock_market.get_history = AsyncMock(return_value=mock_history)

        response = await client.get("/api/chart/AAPL?days=30")

        assert response.status_code == 200
        assert response.json()["symbol"] == "AAPL"

    @patch("app.api.routes.market_service")
    @pytest.mark.asyncio
    async def test_get_chart_no_data(self, mock_market, client):
        from app.models.schemas import HistoryData

        mock_history = HistoryData(
            symbol="INVALID",
            days=30,
            data=[],
            source="unavailable",
            timestamp="2024-03-05T10:00:00",
        )
        mock_market.get_history = AsyncMock(return_value=mock_history)

        response = await client.get("/api/chart/INVALID?days=30")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_chart_invalid_days(self, client):
        assert (await client.get("/api/chart/AAPL?days=5")).status_code == 422
        assert (await client.get("/api/chart/AAPL?days=400")).status_code == 422


class TestChatEndpoint:
    @patch("app.api.routes.enricher")
    @patch("app.api.routes.agent")
    @pytest.mark.asyncio
    async def test_chat_endpoint_structure(self, mock_agent, mock_enricher, client):
        mock_enricher.enrich.return_value = "enriched query"

        async def mock_run(query, model_name=None):
            yield SSEEvent(type="chunk", text="test")
            yield SSEEvent(type="done")

        mock_agent.run = mock_run

        response = await client.post("/api/chat", json={"query": "test query"})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
