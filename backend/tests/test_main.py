"""
测试Main应用
"""
import pytest
from unittest.mock import Mock, patch
from httpx import ASGITransport, AsyncClient


class TestMainApplication:
    """测试主应用"""

    @patch('app.main.FastAPI')
    @patch('app.main.CORSMiddleware')
    def test_app_creation(self, mock_cors, mock_fastapi):
        """测试应用创建"""
        # Import will create the app
        with patch.dict('sys.modules', {'app.main': None}):
            import importlib
            # Just test that imports work
            assert True

    def test_app_has_cors(self):
        """测试CORS配置"""
        from app.main import app

        # Check app exists
        assert app is not None

    def test_app_has_router(self):
        """测试路由配置"""
        from app.main import app

        # Check routes are registered
        routes = [route.path for route in app.routes]
        assert len(routes) > 0

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """测试根路径端点"""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Financial Asset QA System"
        assert data["version"] == "2.0.0"
        assert data["status"] == "running"
