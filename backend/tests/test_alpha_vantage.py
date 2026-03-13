"""
测试 Alpha Vantage 降级逻辑
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.market.service import MarketDataService
from app.models.schemas import MarketData


class TestAlphaVantageFallback:
    """测试 Alpha Vantage 降级逻辑"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        with patch('app.market.service.redis.Redis'):
            return MarketDataService()

    @pytest.mark.asyncio
    async def test_alpha_vantage_success(self, service):
        """测试 Alpha Vantage 成功获取数据"""
        mock_response = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "150.25",
                "10. change percent": "2.5%"
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=Mock(
                    status_code=200,
                    json=Mock(return_value=mock_response)
                )
            )

            with patch('app.config.settings.ALPHA_VANTAGE_API_KEY', 'test_key'):
                result = await service._fetch_alpha_vantage('AAPL')

                assert result is not None
                assert result.symbol == 'AAPL'
                assert result.price == 150.25
                assert result.source == 'alpha_vantage'

    @pytest.mark.asyncio
    async def test_alpha_vantage_no_api_key(self, service):
        """测试没有 API Key 的情况"""
        with patch('app.config.settings.ALPHA_VANTAGE_API_KEY', None):
            result = await service._fetch_alpha_vantage('AAPL')
            assert result is None

    @pytest.mark.asyncio
    async def test_yfinance_to_alpha_vantage_fallback(self, service):
        """测试从 yfinance 降级到 Alpha Vantage"""
        service.redis_client.get = Mock(return_value=None)

        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_ticker.return_value.info = {}

            mock_av_response = {
                "Global Quote": {
                    "01. symbol": "AAPL",
                    "05. price": "150.25",
                    "10. change percent": "2.5%"
                }
            }

            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=Mock(
                        status_code=200,
                        json=Mock(return_value=mock_av_response)
                    )
                )

                with patch('app.config.settings.ALPHA_VANTAGE_API_KEY', 'test_key'):
                    result = await service.get_price('AAPL')

                    assert result.source == 'alpha_vantage'
                    assert result.price == 150.25

    @pytest.mark.asyncio
    async def test_both_sources_fail(self, service):
        """测试两个数据源都失败"""
        service.redis_client.get = Mock(return_value=None)

        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_ticker.return_value.info = {}

            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=Mock(status_code=500)
                )

                with patch('app.config.settings.ALPHA_VANTAGE_API_KEY', 'test_key'):
                    result = await service.get_price('AAPL')

                    assert result.source == 'unavailable'
                    assert result.error is not None
