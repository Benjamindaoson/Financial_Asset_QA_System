"""
测试Pydantic模型和schemas
"""
import pytest
from datetime import datetime
from app.models.schemas import (
    PricePoint,
    MarketData,
    HistoryData,
    ChangeData,
    CompanyInfo,
    Document,
    KnowledgeResult,
    SearchResult,
    WebSearchResult,
    ChatRequest,
    Source,
    SSEEvent,
    HealthResponse,
    ChartResponse,
    ToolCall,
    ToolResult
)


class TestPricePoint:
    """测试PricePoint模型"""

    def test_price_point_creation(self):
        """测试创建价格点"""
        point = PricePoint(
            date="2024-03-05",
            open=150.0,
            high=152.0,
            low=148.0,
            close=151.0,
            volume=1000000
        )

        assert point.date == "2024-03-05"
        assert point.open == 150.0
        assert point.high == 152.0
        assert point.low == 148.0
        assert point.close == 151.0
        assert point.volume == 1000000

    def test_price_point_validation(self):
        """测试价格点验证"""
        with pytest.raises(Exception):
            PricePoint(
                date="2024-03-05",
                open=150.0,
                high=152.0,
                low=148.0,
                close=151.0
                # missing volume
            )


class TestMarketData:
    """测试MarketData模型"""

    def test_market_data_creation(self):
        """测试创建市场数据"""
        data = MarketData(
            symbol="AAPL",
            price=150.0,
            currency="USD",
            name="Apple Inc.",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )

        assert data.symbol == "AAPL"
        assert data.price == 150.0
        assert data.currency == "USD"
        assert data.name == "Apple Inc."
        assert data.source == "yfinance"

    def test_market_data_with_error(self):
        """测试带错误的市场数据"""
        data = MarketData(
            symbol="INVALID",
            source="yfinance",
            timestamp="2024-03-05T10:00:00",
            error="Symbol not found"
        )

        assert data.symbol == "INVALID"
        assert data.error == "Symbol not found"
        assert data.price is None


class TestHistoryData:
    """测试HistoryData模型"""

    def test_history_data_creation(self):
        """测试创建历史数据"""
        data = HistoryData(
            symbol="AAPL",
            days=30,
            data=[
                PricePoint(
                    date="2024-03-05",
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

        assert data.symbol == "AAPL"
        assert data.days == 30
        assert len(data.data) == 1
        assert data.data[0].close == 151.0


class TestChangeData:
    """测试ChangeData模型"""

    def test_change_data_creation(self):
        """测试创建涨跌数据"""
        data = ChangeData(
            symbol="AAPL",
            days=7,
            start_price=145.0,
            end_price=150.0,
            change_pct=3.45,
            trend="上涨",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )

        assert data.symbol == "AAPL"
        assert data.days == 7
        assert data.start_price == 145.0
        assert data.end_price == 150.0
        assert data.change_pct == 3.45
        assert data.trend == "上涨"

    def test_change_data_trend_values(self):
        """测试趋势值"""
        # 上涨
        data1 = ChangeData(
            symbol="AAPL",
            days=7,
            start_price=145.0,
            end_price=150.0,
            change_pct=3.45,
            trend="上涨",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        assert data1.trend == "上涨"

        # 下跌
        data2 = ChangeData(
            symbol="AAPL",
            days=7,
            start_price=150.0,
            end_price=145.0,
            change_pct=-3.33,
            trend="下跌",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        assert data2.trend == "下跌"

        # 震荡
        data3 = ChangeData(
            symbol="AAPL",
            days=7,
            start_price=150.0,
            end_price=150.5,
            change_pct=0.33,
            trend="震荡",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        assert data3.trend == "震荡"


class TestCompanyInfo:
    """测试CompanyInfo模型"""

    def test_company_info_creation(self):
        """测试创建公司信息"""
        info = CompanyInfo(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            market_cap=3000000000000,
            pe_ratio=28.5,
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )

        assert info.symbol == "AAPL"
        assert info.name == "Apple Inc."
        assert info.sector == "Technology"
        assert info.market_cap == 3000000000000
        assert info.pe_ratio == 28.5


class TestDocument:
    """测试Document模型"""

    def test_document_creation(self):
        """测试创建文档"""
        doc = Document(
            content="市盈率是股票价格与每股收益的比率",
            source="knowledge_base",
            score=0.85
        )

        assert doc.content == "市盈率是股票价格与每股收益的比率"
        assert doc.source == "knowledge_base"
        assert doc.score == 0.85


class TestKnowledgeResult:
    """测试KnowledgeResult模型"""

    def test_knowledge_result_creation(self):
        """测试创建知识检索结果"""
        result = KnowledgeResult(
            documents=[
                Document(
                    content="市盈率是股票价格与每股收益的比率",
                    source="knowledge_base",
                    score=0.85
                )
            ],
            total_found=1
        )

        assert len(result.documents) == 1
        assert result.total_found == 1
        assert result.documents[0].score == 0.85


class TestSearchResult:
    """测试SearchResult模型"""

    def test_search_result_creation(self):
        """测试创建搜索结果"""
        result = SearchResult(
            title="Apple Stock Rises",
            snippet="Apple stock increased by 3% today...",
            url="https://example.com/news",
            published="2024-03-05"
        )

        assert result.title == "Apple Stock Rises"
        assert result.snippet == "Apple stock increased by 3% today..."
        assert result.url == "https://example.com/news"
        assert result.published == "2024-03-05"


class TestWebSearchResult:
    """测试WebSearchResult模型"""

    def test_web_search_result_creation(self):
        """测试创建网络搜索结果"""
        result = WebSearchResult(
            results=[
                SearchResult(
                    title="Apple Stock Rises",
                    snippet="Apple stock increased by 3% today...",
                    url="https://example.com/news"
                )
            ],
            search_query="Apple stock news"
        )

        assert len(result.results) == 1
        assert result.search_query == "Apple stock news"


class TestChatRequest:
    """测试ChatRequest模型"""

    def test_chat_request_creation(self):
        """测试创建聊天请求"""
        request = ChatRequest(
            query="苹果股价",
            session_id="test-session-123"
        )

        assert request.query == "苹果股价"
        assert request.session_id == "test-session-123"

    def test_chat_request_validation(self):
        """测试聊天请求验证"""
        # 空查询应该失败
        with pytest.raises(Exception):
            ChatRequest(query="")

        # 超长查询应该失败
        with pytest.raises(Exception):
            ChatRequest(query="a" * 501)


class TestSource:
    """测试Source模型"""

    def test_source_creation(self):
        """测试创建数据源"""
        source = Source(
            name="yfinance",
            timestamp="2024-03-05T10:00:00"
        )

        assert source.name == "yfinance"
        assert source.timestamp == "2024-03-05T10:00:00"


class TestSSEEvent:
    """测试SSEEvent模型"""

    def test_sse_event_tool_start(self):
        """测试工具启动事件"""
        event = SSEEvent(
            type="tool_start",
            name="get_price",
            display="正在获取价格..."
        )

        assert event.type == "tool_start"
        assert event.name == "get_price"
        assert event.display == "正在获取价格..."

    def test_sse_event_chunk(self):
        """测试文本块事件"""
        event = SSEEvent(
            type="chunk",
            text="苹果公司的股价是"
        )

        assert event.type == "chunk"
        assert event.text == "苹果公司的股价是"

    def test_sse_event_done(self):
        """测试完成事件"""
        event = SSEEvent(
            type="done",
            verified=True,
            sources=[Source(name="yfinance", timestamp="2024-03-05T10:00:00")],
            request_id="test-123"
        )

        assert event.type == "done"
        assert event.verified is True
        assert len(event.sources) == 1
        assert event.request_id == "test-123"

    def test_sse_event_error(self):
        """测试错误事件"""
        event = SSEEvent(
            type="error",
            message="API调用失败",
            code="API_ERROR"
        )

        assert event.type == "error"
        assert event.message == "API调用失败"
        assert event.code == "API_ERROR"

    def test_sse_event_model_selected(self):
        """测试模型选择事件"""
        event = SSEEvent(
            type="model_selected",
            model="claude-opus",
            provider="anthropic",
            complexity="simple"
        )

        assert event.type == "model_selected"
        assert event.model == "claude-opus"
        assert event.provider == "anthropic"


class TestHealthResponse:
    """测试HealthResponse模型"""

    def test_health_response_creation(self):
        """测试创建健康检查响应"""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp="2024-03-05T10:00:00",
            components={
                "redis": "connected",
                "chromadb": "ready",
                "claude_api": "configured"
            }
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.components["redis"] == "connected"


class TestChartResponse:
    """测试ChartResponse模型"""

    def test_chart_response_creation(self):
        """测试创建图表响应"""
        response = ChartResponse(
            symbol="AAPL",
            data=[
                PricePoint(
                    date="2024-03-05",
                    open=150.0,
                    high=152.0,
                    low=148.0,
                    close=151.0,
                    volume=1000000
                )
            ],
            source="yfinance"
        )

        assert response.symbol == "AAPL"
        assert len(response.data) == 1
        assert response.source == "yfinance"


class TestToolCall:
    """测试ToolCall模型"""

    def test_tool_call_creation(self):
        """测试创建工具调用"""
        call = ToolCall(
            name="get_price",
            params={"symbol": "AAPL"}
        )

        assert call.name == "get_price"
        assert call.params["symbol"] == "AAPL"


class TestToolResult:
    """测试ToolResult模型"""

    def test_tool_result_creation(self):
        """测试创建工具结果"""
        result = ToolResult(
            tool="get_price",
            data={"price": 150.0},
            latency_ms=250,
            status="success",
            data_source="yfinance",
            cache_hit=False
        )

        assert result.tool == "get_price"
        assert result.data["price"] == 150.0
        assert result.latency_ms == 250
        assert result.status == "success"
        assert result.cache_hit is False

    def test_tool_result_with_error(self):
        """测试带错误的工具结果"""
        result = ToolResult(
            tool="get_price",
            data={},
            latency_ms=100,
            status="error",
            data_source="yfinance",
            cache_hit=False,
            error_message="Symbol not found"
        )

        assert result.status == "error"
        assert result.error_message == "Symbol not found"
