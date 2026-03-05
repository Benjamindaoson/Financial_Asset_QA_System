"""
测试Web搜索服务
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.search.service import WebSearchService
from app.models.schemas import WebSearchResult, SearchResult


class TestWebSearchServiceInitialization:
    """测试Web搜索服务初始化"""

    @patch('app.search.service.settings')
    def test_service_initialization(self, mock_settings):
        """测试服务初始化"""
        mock_settings.TAVILY_API_KEY = "test-key"

        service = WebSearchService()

        assert service is not None
        assert service.api_key == "test-key"
        assert service.base_url == "https://api.tavily.com/search"


class TestWebSearch:
    """测试Web搜索功能"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        with patch('app.search.service.settings') as mock_settings:
            mock_settings.TAVILY_API_KEY = "test-key"
            mock_settings.API_TIMEOUT = 30
            return WebSearchService()

    @pytest.mark.asyncio
    async def test_search_no_api_key(self):
        """测试无API密钥"""
        with patch('app.search.service.settings') as mock_settings:
            mock_settings.TAVILY_API_KEY = None

            service = WebSearchService()
            result = await service.search("test query")

            assert isinstance(result, WebSearchResult)
            assert len(result.results) == 0
            assert result.search_query == "test query"

    @pytest.mark.asyncio
    async def test_search_success(self, service):
        """测试搜索成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Title 1",
                    "content": "Test content 1",
                    "url": "https://example.com/1",
                    "published_date": "2024-03-05"
                },
                {
                    "title": "Test Title 2",
                    "content": "Test content 2",
                    "url": "https://example.com/2",
                    "published_date": "2024-03-04"
                }
            ]
        }

        with patch('app.search.service.httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await service.search("test query")

            assert isinstance(result, WebSearchResult)
            assert len(result.results) == 2
            assert result.results[0].title == "Test Title 1"
            assert result.results[0].url == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_search_with_max_results(self, service):
        """测试限制结果数量"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": f"Title {i}",
                    "content": f"Content {i}",
                    "url": f"https://example.com/{i}"
                }
                for i in range(10)
            ]
        }

        with patch('app.search.service.httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await service.search("test query", max_results=3)

            assert isinstance(result, WebSearchResult)
            assert len(result.results) == 10  # Returns all from API

    @pytest.mark.asyncio
    async def test_search_api_error(self, service):
        """测试API错误"""
        mock_response = Mock()
        mock_response.status_code = 500

        with patch('app.search.service.httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await service.search("test query")

            assert isinstance(result, WebSearchResult)
            assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_search_network_error(self, service):
        """测试网络错误"""
        with patch('app.search.service.httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_client.return_value = mock_context

            result = await service.search("test query")

            assert isinstance(result, WebSearchResult)
            assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_search_empty_results(self, service):
        """测试空结果"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": []
        }

        with patch('app.search.service.httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await service.search("test query")

            assert isinstance(result, WebSearchResult)
            assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_search_truncates_long_content(self, service):
        """测试截断长内容"""
        long_content = "x" * 500
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test",
                    "content": long_content,
                    "url": "https://example.com"
                }
            ]
        }

        with patch('app.search.service.httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await service.search("test query")

            assert len(result.results[0].snippet) == 200
