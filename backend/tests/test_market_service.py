"""
测试市场数据服务
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.market.service import MarketDataService
from app.models.schemas import MarketData, HistoryData, ChangeData, CompanyInfo


class TestMarketDataService:
    """测试MarketDataService类"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        with patch('app.market.service.redis.Redis'):
            return MarketDataService()

    @pytest.mark.asyncio
    async def test_get_price_success(self, service):
        """测试成功获取价格"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_info = {
                'regularMarketPrice': 150.0,
                'currency': 'USD',
                'longName': 'Apple Inc.'
            }
            mock_ticker.return_value.info = mock_info

            result = await service.get_price('AAPL')

            assert isinstance(result, MarketData)
            assert result.symbol == 'AAPL'
            assert result.price == 150.0
            assert result.currency == 'USD'
            assert result.name == 'Apple Inc.'

    @pytest.mark.asyncio
    async def test_get_price_invalid_symbol(self, service):
        """测试获取无效股票代码的价格"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_ticker.return_value.info = {}

            result = await service.get_price('INVALID')

            assert isinstance(result, MarketData)
            assert result.symbol == 'INVALID'
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_get_history_success(self, service):
        """测试成功获取历史数据"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            import pandas as pd
            mock_history = pd.DataFrame({
                'Open': [148.0, 149.0],
                'High': [152.0, 153.0],
                'Low': [147.0, 148.0],
                'Close': [150.0, 151.0],
                'Volume': [1000000, 1100000]
            }, index=pd.DatetimeIndex(['2024-03-01', '2024-03-02']))

            mock_ticker.return_value.history.return_value = mock_history

            result = await service.get_history('AAPL', 30)

            assert isinstance(result, HistoryData)
            assert result.symbol == 'AAPL'
            assert result.days == 30
            assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_get_change_success(self, service):
        """测试成功获取涨跌幅"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            import pandas as pd
            mock_history = pd.DataFrame({
                'Open': [144.0, 149.0],
                'High': [146.0, 151.0],
                'Low': [143.0, 148.0],
                'Close': [145.0, 150.0],
                'Volume': [1000000, 1100000]
            }, index=pd.DatetimeIndex(['2024-03-01', '2024-03-07']))

            mock_ticker.return_value.history.return_value = mock_history

            result = await service.get_change('AAPL', 7)

            assert isinstance(result, ChangeData)
            assert result.symbol == 'AAPL'
            assert result.days == 7
            assert result.start_price == 145.0
            assert result.end_price == 150.0
            assert result.change_pct > 0

    @pytest.mark.asyncio
    async def test_get_info_success(self, service):
        """测试成功获取公司信息"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_info = {
                'longName': 'Apple Inc.',
                'sector': 'Technology',
                'industry': 'Consumer Electronics',
                'marketCap': 3000000000000,
                'trailingPE': 28.5,
                'fiftyTwoWeekHigh': 200.0,
                'fiftyTwoWeekLow': 120.0,
                'longBusinessSummary': 'Apple designs and manufactures...'
            }
            mock_ticker.return_value.info = mock_info

            result = await service.get_info('AAPL')

            assert isinstance(result, CompanyInfo)
            assert result.symbol == 'AAPL'
            assert result.name == 'Apple Inc.'
            assert result.sector == 'Technology'

    @pytest.mark.asyncio
    async def test_cache_hit(self, service):
        """测试缓存命中"""
        import json

        cached_data = {
            'symbol': 'AAPL',
            'price': 150.0,
            'currency': 'USD',
            'name': 'Apple Inc.',
            'source': 'cache',
            'timestamp': '2024-03-05T10:00:00'
        }

        service.redis_client.get = Mock(return_value=json.dumps(cached_data))

        result = await service.get_price('AAPL')

        assert result.source == 'cache'
        assert result.price == 150.0

    @pytest.mark.asyncio
    async def test_cache_miss(self, service):
        """测试缓存未命中"""
        service.redis_client.get = Mock(return_value=None)

        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_info = {
                'regularMarketPrice': 150.0,
                'currency': 'USD',
                'longName': 'Apple Inc.'
            }
            mock_ticker.return_value.info = mock_info

            result = await service.get_price('AAPL')

            assert result.source == 'yfinance'
            service.redis_client.setex.assert_called_once()


class TestMarketDataServiceEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        with patch('app.market.service.redis.Redis'):
            return MarketDataService()

    @pytest.mark.asyncio
    async def test_empty_symbol(self, service):
        """测试空股票代码"""
        result = await service.get_price('')

        assert isinstance(result, MarketData)
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_special_characters_symbol(self, service):
        """测试包含特殊字符的股票代码"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_info = {
                'regularMarketPrice': 100.0,
                'currency': 'USD',
                'shortName': 'Test Company'
            }
            mock_ticker.return_value.info = mock_info

            result = await service.get_price('BRK.B')

            assert isinstance(result, MarketData)

    @pytest.mark.asyncio
    async def test_negative_days(self, service):
        """测试负数天数"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            import pandas as pd
            mock_history = pd.DataFrame({
                'Open': [148.0],
                'High': [152.0],
                'Low': [147.0],
                'Close': [150.0],
                'Volume': [1000000]
            }, index=pd.DatetimeIndex(['2024-03-01']))

            mock_ticker.return_value.history.return_value = mock_history

            # 应该使用绝对值或默认值
            result = await service.get_history('AAPL', -30)

            assert isinstance(result, HistoryData)

    @pytest.mark.asyncio
    async def test_zero_days(self, service):
        """测试零天数"""
        with patch('app.market.service.yf.Ticker') as mock_ticker:
            import pandas as pd
            mock_history = pd.DataFrame({
                'Open': [148.0],
                'High': [152.0],
                'Low': [147.0],
                'Close': [150.0],
                'Volume': [1000000]
            }, index=pd.DatetimeIndex(['2024-03-01']))

            mock_ticker.return_value.history.return_value = mock_history

            result = await service.get_history('AAPL', 0)

            assert isinstance(result, HistoryData)

    @pytest.mark.asyncio
    async def test_redis_connection_error(self, service):
        """测试Redis连接错误"""
        service.redis_client.get = Mock(side_effect=Exception("Connection error"))

        with patch('app.market.service.yf.Ticker') as mock_ticker:
            mock_info = {
                'regularMarketPrice': 150.0,
                'currency': 'USD',
                'shortName': 'Apple Inc.'
            }
            mock_ticker.return_value.info = mock_info

            # 应该降级到直接获取数据
            result = await service.get_price('AAPL')

            assert isinstance(result, MarketData)
            assert result.price == 150.0


class TestTickerMapper:
    """测试股票代码映射"""

    def test_normalize_chinese_name(self):
        """测试中文名称映射"""
        from app.market.service import TickerMapper

        assert TickerMapper.normalize("苹果") == "AAPL"
        assert TickerMapper.normalize("茅台") == "600519.SS"
        assert TickerMapper.normalize("腾讯") == "0700.HK"

    def test_normalize_a_share(self):
        """测试A股代码转换"""
        from app.market.service import TickerMapper

        # 上海股票
        assert TickerMapper.normalize("600519") == "600519.SS"
        # 深圳股票
        assert TickerMapper.normalize("000001") == "000001.SZ"
        assert TickerMapper.normalize("300750") == "300750.SZ"

    def test_normalize_passthrough(self):
        """测试直接通过"""
        from app.market.service import TickerMapper

        assert TickerMapper.normalize("AAPL") == "AAPL"
        assert TickerMapper.normalize("TSLA") == "TSLA"
