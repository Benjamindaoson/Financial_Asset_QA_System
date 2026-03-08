"""Tests for the grounded agent core."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agent.core import AgentCore, ResponseGuard
from app.models.multi_model import ModelConfig, ModelProvider, QueryComplexity
from app.models.schemas import ChangeData, CompanyInfo, HistoryData, MarketData


def build_test_agent(preferred_model=None):
    with patch("app.agent.core.MarketDataService"), patch("app.agent.core.HybridRAGPipeline"), patch(
        "app.agent.core.ConfidenceScorer"
    ), patch("app.agent.core.WebSearchService"):
        agent = AgentCore(preferred_model=preferred_model)

    agent.model_manager.models["deepseek-chat"] = ModelConfig(
        provider=ModelProvider.DEEPSEEK,
        model_name="deepseek-chat",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )
    agent.model_manager.usage_stats["deepseek-chat"] = {
        "total_requests": 0,
        "total_tokens_input": 0,
        "total_tokens_output": 0,
        "total_cost": 0.0,
        "errors": 0,
    }
    for complexity in QueryComplexity:
        agent.model_manager.routing_rules[complexity] = ["deepseek-chat"]
    return agent


class TestResponseGuard:
    def test_validate_returns_true_for_empty_grounding(self):
        assert ResponseGuard.validate("test response", []) is True


class TestAgentCoreInitialization:
    def test_agent_initialization(self):
        agent = build_test_agent()

        assert agent.model_manager is not None
        assert agent.preferred_model is None
        assert len(agent.tools) == 6

    def test_agent_with_preferred_model(self):
        agent = build_test_agent(preferred_model="deepseek-chat")
        assert agent.preferred_model == "deepseek-chat"


class TestToolExecution:
    @pytest.fixture
    def agent(self):
        return build_test_agent()

    @pytest.mark.asyncio
    async def test_execute_get_price(self, agent):
        agent.market_service.get_price = AsyncMock(
            return_value=MarketData(
                symbol="AAPL",
                price=150.0,
                currency="USD",
                name="Apple Inc.",
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        result = await agent._execute_tool("get_price", {"symbol": "AAPL"})

        assert result["success"] is True
        assert result["data"]["price"] == 150.0

    @pytest.mark.asyncio
    async def test_execute_get_history(self, agent):
        agent.market_service.get_history = AsyncMock(
            return_value=HistoryData(
                symbol="AAPL",
                days=30,
                data=[],
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        result = await agent._execute_tool("get_history", {"symbol": "AAPL", "days": 30})

        assert result["success"] is True
        assert result["data"]["days"] == 30

    @pytest.mark.asyncio
    async def test_execute_get_change(self, agent):
        agent.market_service.get_change = AsyncMock(
            return_value=ChangeData(
                symbol="AAPL",
                days=7,
                start_price=145.0,
                end_price=150.0,
                change_pct=3.45,
                trend="上涨",
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        result = await agent._execute_tool("get_change", {"symbol": "AAPL", "days": 7})

        assert result["success"] is True
        assert result["data"]["change_pct"] == 3.45

    @pytest.mark.asyncio
    async def test_execute_get_info(self, agent):
        agent.market_service.get_info = AsyncMock(
            return_value=CompanyInfo(
                symbol="AAPL",
                name="Apple Inc.",
                sector="Technology",
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        result = await agent._execute_tool("get_info", {"symbol": "AAPL"})

        assert result["success"] is True
        assert result["data"]["name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, agent):
        result = await agent._execute_tool("unknown_tool", {})
        assert result["status"] == "error"


class TestModelSelection:
    @pytest.fixture
    def agent(self):
        return build_test_agent()

    def test_select_model_with_preferred(self, agent):
        agent.preferred_model = "deepseek-chat"
        assert agent._select_model("测试") == "deepseek-chat"

    def test_select_model_auto(self, agent):
        agent.preferred_model = None
        model = agent._select_model("什么是市盈率？")
        assert model == "deepseek-chat"


class TestAgentRun:
    @pytest.fixture
    def agent(self):
        return build_test_agent()

    @pytest.mark.asyncio
    async def test_run_with_model_not_found(self, agent):
        events = [event async for event in agent.run("测试", model_name="nonexistent-model")]
        assert events[0].type == "error"
        assert "not found" in events[0].message.lower()

    @pytest.mark.asyncio
    async def test_run_streaming_with_text_chunks(self, agent):
        mock_adapter = Mock()

        async def mock_stream(*args, **kwargs):
            text_event = Mock()
            text_event.type = "content_block_delta"
            text_event.delta = Mock()
            text_event.delta.type = "text_delta"
            text_event.delta.text = "测试文本"
            yield text_event
            yield {"final_message": Mock(content=[Mock(type="text", text="测试文本")])}

        mock_adapter.create_message_stream = Mock(side_effect=mock_stream)

        with patch("app.agent.core.ModelAdapterFactory.create_adapter", return_value=mock_adapter):
            events = [event async for event in agent.run("测试查询")]

        assert any(event.type == "model_selected" for event in events)
        assert any(event.type == "chunk" for event in events)
        assert any(event.type == "done" for event in events)

    @pytest.mark.asyncio
    async def test_run_streaming_with_tool_results(self, agent):
        mock_adapter = Mock()

        async def mock_stream(*args, **kwargs):
            text_event = Mock()
            text_event.type = "content_block_delta"
            text_event.delta = Mock()
            text_event.delta.type = "text_delta"
            text_event.delta.text = "基于数据的回答"
            yield text_event
            yield {"final_message": Mock(content=[Mock(type="text", text="基于数据的回答")])}

        mock_adapter.create_message_stream = Mock(side_effect=mock_stream)
        agent.market_service.get_price = AsyncMock(
            return_value=MarketData(
                symbol="AAPL",
                price=150.0,
                currency="USD",
                name="Apple Inc.",
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        with patch("app.agent.core.ModelAdapterFactory.create_adapter", return_value=mock_adapter):
            events = [event async for event in agent.run("AAPL价格")]

        assert any(event.type == "tool_start" for event in events)
        assert any(event.type == "tool_data" for event in events)
        assert any(event.type == "done" for event in events)

    @pytest.mark.asyncio
    async def test_run_with_exception_handling(self, agent):
        mock_adapter = Mock()

        async def mock_stream(*args, **kwargs):
            raise Exception("API Error")
            yield

        mock_adapter.create_message_stream = Mock(side_effect=mock_stream)

        with patch("app.agent.core.ModelAdapterFactory.create_adapter", return_value=mock_adapter):
            events = [event async for event in agent.run("测试")]

        error_event = next(event for event in events if event.type == "error")
        assert "API Error" in error_event.message or error_event.code == "LLM_ERROR"
