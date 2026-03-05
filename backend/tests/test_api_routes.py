"""
测试API Routes
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.api.routes import router
from app.models.schemas import ChatRequest, HealthResponse, ChartResponse, SSEEvent, PricePoint


@pytest.fixture
def app():
    """创建测试应用"""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


class TestHealthEndpoint:
    """测试健康检查端点"""

    @patch('app.api.routes.market_service')
    @patch('app.api.routes.agent')
    @patch('app.api.routes.settings')
    def test_health_all_healthy(self, mock_settings, mock_agent, mock_market, client):
        """测试所有组件健康"""
        # Mock Redis
        mock_market.redis_client.ping.return_value = True

        # Mock ChromaDB
        mock_agent.rag_pipeline.get_collection_count.return_value = 100

        # Mock settings
        mock_settings.ANTHROPIC_API_KEY = "test-key"

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data
        assert data["components"]["redis"] == "connected"
        assert data["components"]["yfinance"] == "available"

    @patch('app.api.routes.market_service')
    @patch('app.api.routes.agent')
    @patch('app.api.routes.settings')
    def test_health_redis_down(self, mock_settings, mock_agent, mock_market, client):
        """测试Redis断开连接"""
        # Mock Redis failure
        mock_market.redis_client.ping.side_effect = Exception("Connection failed")

        # Mock ChromaDB
        mock_agent.rag_pipeline.get_collection_count.return_value = 100

        # Mock settings
        mock_settings.ANTHROPIC_API_KEY = "test-key"

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"] == "disconnected"

    @patch('app.api.routes.market_service')
    @patch('app.api.routes.agent')
    @patch('app.api.routes.settings')
    def test_health_no_api_key(self, mock_settings, mock_agent, mock_market, client):
        """测试未配置API密钥"""
        # Mock Redis
        mock_market.redis_client.ping.return_value = True

        # Mock ChromaDB
        mock_agent.rag_pipeline.get_collection_count.return_value = 100

        # Mock settings - no API key
        mock_settings.ANTHROPIC_API_KEY = None

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["claude_api"] == "not_configured"


class TestModelsEndpoint:
    """测试模型列表端点"""

    @patch('app.api.routes.agent')
    def test_list_models(self, mock_agent, client):
        """测试获取模型列表"""
        mock_agent.get_available_models.return_value = [
            {"name": "claude-3-5-sonnet-20241022", "provider": "anthropic"},
            {"name": "deepseek-chat", "provider": "deepseek"}
        ]
        mock_agent.get_usage_report.return_value = {
            "total_requests": 100,
            "total_tokens": 50000
        }

        response = client.get("/api/models")

        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "usage" in data
        assert len(data["models"]) == 2


class TestChartEndpoint:
    """测试图表数据端点"""

    @patch('app.api.routes.market_service')
    @pytest.mark.asyncio
    async def test_get_chart_success(self, mock_market, client):
        """测试成功获取图表数据"""
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
                    volume=1000000
                )
            ],
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        mock_market.get_history = AsyncMock(return_value=mock_history)

        response = client.get("/api/chart/AAPL?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert len(data["data"]) == 1

    @patch('app.api.routes.market_service')
    @pytest.mark.asyncio
    async def test_get_chart_no_data(self, mock_market, client):
        """测试无数据情况"""
        from app.models.schemas import HistoryData

        mock_history = HistoryData(
            symbol="INVALID",
            days=30,
            data=[],
            source="unavailable",
            timestamp="2024-03-05T10:00:00"
        )
        mock_market.get_history = AsyncMock(return_value=mock_history)

        response = client.get("/api/chart/INVALID?days=30")

        assert response.status_code == 404

    def test_get_chart_invalid_days_too_small(self, client):
        """测试天数太小"""
        response = client.get("/api/chart/AAPL?days=5")

        assert response.status_code == 422

    def test_get_chart_invalid_days_too_large(self, client):
        """测试天数太大"""
        response = client.get("/api/chart/AAPL?days=400")

        assert response.status_code == 422


class TestChatEndpoint:
    """测试聊天端点"""

    @patch('app.api.routes.enricher')
    @patch('app.api.routes.agent')
    def test_chat_endpoint_structure(self, mock_agent, mock_enricher, client):
        """测试聊天端点结构"""
        mock_enricher.enrich.return_value = "enriched query"

        # Mock async generator
        async def mock_run(query, model_name=None):
            yield SSEEvent(type="chunk", text="test")
            yield SSEEvent(type="done")

        mock_agent.run = mock_run

        response = client.post(
            "/api/chat",
            json={"query": "test query"}
        )

        # SSE endpoint should return 200
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestRouterIntegration:
    """测试路由集成"""

    def test_all_routes_registered(self, app):
        """测试所有路由已注册"""
        routes = [route.path for route in app.routes]

        assert "/api/health" in routes
        assert "/api/models" in routes
        assert "/api/chat" in routes
        assert "/api/chart/{symbol}" in routes
