"""
测试Agent Core
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.agent.core import AgentCore, ResponseGuard
from app.models.schemas import SSEEvent, MarketData, HistoryData, ChangeData, CompanyInfo


class TestResponseGuard:
    """测试ResponseGuard类"""

    def test_validate_returns_true(self):
        """测试验证总是返回True"""
        result = ResponseGuard.validate("test response", [])
        assert result is True


class TestAgentCoreInitialization:
    """测试AgentCore初始化"""

    @patch('app.agent.core.MarketDataService')
    @patch('app.agent.core.HybridRAGPipeline')
    @patch('app.agent.core.ConfidenceScorer')
    @patch('app.agent.core.WebSearchService')
    def test_agent_initialization(self, mock_search, mock_scorer, mock_rag, mock_market):
        """测试Agent初始化"""
        agent = AgentCore()

        assert agent is not None
        assert agent.model_manager is not None
        assert agent.preferred_model is None
        assert agent.tools is not None
        assert len(agent.tools) == 6

    @patch('app.agent.core.MarketDataService')
    @patch('app.agent.core.HybridRAGPipeline')
    @patch('app.agent.core.ConfidenceScorer')
    @patch('app.agent.core.WebSearchService')
    def test_agent_with_preferred_model(self, mock_search, mock_scorer, mock_rag, mock_market):
        """测试指定首选模型"""
        agent = AgentCore(preferred_model="claude-3-5-sonnet-20241022")

        assert agent.preferred_model == "claude-3-5-sonnet-20241022"


class TestAgentTools:
    """测试Agent工具定义"""

    @patch('app.agent.core.MarketDataService')
    @patch('app.agent.core.HybridRAGPipeline')
    @patch('app.agent.core.ConfidenceScorer')
    @patch('app.agent.core.WebSearchService')
    def test_tools_structure(self, mock_search, mock_scorer, mock_rag, mock_market):
        """测试工具结构"""
        agent = AgentCore()

        tool_names = [tool["name"] for tool in agent.tools]
        assert "get_price" in tool_names
        assert "get_history" in tool_names
        assert "get_change" in tool_names
        assert "get_info" in tool_names
        assert "search_knowledge" in tool_names
        assert "search_web" in tool_names

    @patch('app.agent.core.MarketDataService')
    @patch('app.agent.core.HybridRAGPipeline')
    @patch('app.agent.core.ConfidenceScorer')
    @patch('app.agent.core.WebSearchService')
    def test_get_price_tool_schema(self, mock_search, mock_scorer, mock_rag, mock_market):
        """测试get_price工具schema"""
        agent = AgentCore()

        get_price_tool = next(t for t in agent.tools if t["name"] == "get_price")
        assert "description" in get_price_tool
        assert "input_schema" in get_price_tool
        assert "symbol" in get_price_tool["input_schema"]["properties"]


class TestToolExecution:
    """测试工具执行"""

    @pytest.fixture
    def agent(self):
        """创建agent实例"""
        with patch('app.agent.core.MarketDataService'), \
             patch('app.agent.core.HybridRAGPipeline'), \
             patch('app.agent.core.ConfidenceScorer'), \
             patch('app.agent.core.WebSearchService'):
            return AgentCore()

    @pytest.mark.asyncio
    async def test_execute_get_price(self, agent):
        """测试执行get_price工具"""
        mock_result = MarketData(
            symbol="AAPL",
            price=150.0,
            currency="USD",
            name="Apple Inc.",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        agent.market_service.get_price = AsyncMock(return_value=mock_result)

        result = await agent._execute_tool("get_price", {"symbol": "AAPL"})

        assert result["success"] is True
        assert result["data"]["symbol"] == "AAPL"
        assert result["data"]["price"] == 150.0
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_execute_get_history(self, agent):
        """测试执行get_history工具"""
        mock_result = HistoryData(
            symbol="AAPL",
            days=30,
            data=[],
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        agent.market_service.get_history = AsyncMock(return_value=mock_result)

        result = await agent._execute_tool("get_history", {"symbol": "AAPL", "days": 30})

        assert result["success"] is True
        assert result["data"]["symbol"] == "AAPL"
        assert result["data"]["days"] == 30

    @pytest.mark.asyncio
    async def test_execute_get_change(self, agent):
        """测试执行get_change工具"""
        mock_result = ChangeData(
            symbol="AAPL",
            days=7,
            start_price=145.0,
            end_price=150.0,
            change_pct=3.45,
            trend="上涨",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        agent.market_service.get_change = AsyncMock(return_value=mock_result)

        result = await agent._execute_tool("get_change", {"symbol": "AAPL", "days": 7})

        assert result["success"] is True
        assert result["data"]["change_pct"] == 3.45

    @pytest.mark.asyncio
    async def test_execute_get_info(self, agent):
        """测试执行get_info工具"""
        mock_result = CompanyInfo(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            source="yfinance",
            timestamp="2024-03-05T10:00:00"
        )
        agent.market_service.get_info = AsyncMock(return_value=mock_result)

        result = await agent._execute_tool("get_info", {"symbol": "AAPL"})

        assert result["success"] is True
        assert result["data"]["name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, agent):
        """测试执行未知工具"""
        result = await agent._execute_tool("unknown_tool", {})

        assert result["success"] is True
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, agent):
        """测试工具执行错误"""
        agent.market_service.get_price = AsyncMock(side_effect=Exception("API Error"))

        result = await agent._execute_tool("get_price", {"symbol": "AAPL"})

        assert result["success"] is False
        assert "error" in result


class TestModelSelection:
    """测试模型选择"""

    @pytest.fixture
    def agent(self):
        """创建agent实例"""
        with patch('app.agent.core.MarketDataService'), \
             patch('app.agent.core.HybridRAGPipeline'), \
             patch('app.agent.core.ConfidenceScorer'), \
             patch('app.agent.core.WebSearchService'):
            return AgentCore()

    def test_select_model_with_preferred(self, agent):
        """测试使用首选模型"""
        agent.preferred_model = "claude-3-5-sonnet-20241022"

        model = agent._select_model("测试查询")

        assert model == "claude-3-5-sonnet-20241022"

    def test_select_model_auto(self, agent):
        """测试自动选择模型"""
        agent.preferred_model = None

        model = agent._select_model("什么是市盈率")

        assert model is not None
        assert isinstance(model, str)


class TestAgentRun:
    """测试Agent运行"""

    @pytest.fixture
    def agent(self):
        """创建agent实例"""
        with patch('app.agent.core.MarketDataService'), \
             patch('app.agent.core.HybridRAGPipeline'), \
             patch('app.agent.core.ConfidenceScorer'), \
             patch('app.agent.core.WebSearchService'):
            return AgentCore()

    @pytest.mark.asyncio
    async def test_run_with_model_not_found(self, agent):
        """测试运行时模型未找到"""
        events = []
        async for event in agent.run("测试", model_name="nonexistent-model"):
            events.append(event)

        assert len(events) > 0
        assert events[0].type == "error"
        assert "not found" in events[0].message.lower()

    @pytest.mark.asyncio
    async def test_get_available_models(self, agent):
        """测试获取可用模型列表"""
        models = agent.get_available_models()

        assert isinstance(models, list)

    @pytest.mark.asyncio
    async def test_get_usage_report(self, agent):
        """测试获取使用报告"""
        report = agent.get_usage_report()

        assert isinstance(report, dict)


class TestToolExecutionExtended:
    """测试工具执行扩展"""

    @pytest.fixture
    def agent(self):
        """创建agent实例"""
        with patch('app.agent.core.MarketDataService'), \
             patch('app.agent.core.HybridRAGPipeline'), \
             patch('app.agent.core.ConfidenceScorer'), \
             patch('app.agent.core.WebSearchService'):
            return AgentCore()

    @pytest.mark.asyncio
    async def test_execute_search_knowledge(self, agent):
        """测试执行search_knowledge工具"""
        from app.models.schemas import KnowledgeResult, Document

        mock_result = KnowledgeResult(
            documents=[
                Document(content="测试文档", source="test", score=0.9)
            ],
            total_found=1
        )
        agent.rag_pipeline.search = AsyncMock(return_value=mock_result)
        agent.confidence_scorer.calculate = Mock(return_value=0.85)
        agent.confidence_scorer.get_confidence_level = Mock(return_value="高")

        result = await agent._execute_tool("search_knowledge", {"query": "测试"})

        assert result["success"] is True
        assert "confidence" in result["data"]
        assert "confidence_level" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_search_web(self, agent):
        """测试执行search_web工具"""
        from app.models.schemas import WebSearchResult

        mock_result = WebSearchResult(
            results=[],
            search_query="测试"
        )
        agent.search_service.search = AsyncMock(return_value=mock_result)

        result = await agent._execute_tool("search_web", {"query": "测试"})

        assert result["success"] is True
        assert "results" in result["data"]
