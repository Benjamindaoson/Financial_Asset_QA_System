"""Tests for the grounded agent core."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agent.core import AgentCore, ResponseGuard
from app.models.multi_model import ModelConfig, ModelProvider, QueryComplexity
from app.models.schemas import (
    ChangeData,
    CompanyInfo,
    HistoryData,
    MarketData,
    PricePoint,
    RiskMetrics,
)
from app.routing import QueryRoute, QueryType
from app.routing.complexity_analyzer import ComplexityScore


def build_test_agent(preferred_model=None):
    with patch("app.agent.core.MarketDataService"), patch("app.agent.core.HybridRAGPipeline"), patch(
        "app.agent.core.ConfidenceScorer"
    ), patch("app.agent.core.WebSearchService"), patch("app.agent.core.SECFilingsService"):
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
        assert len(agent.tools) >= 9

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
    async def test_execute_get_metrics(self, agent):
        agent.market_service.get_metrics = AsyncMock(
            return_value=RiskMetrics(
                symbol="AAPL",
                range_key="1y",
                annualized_volatility=22.5,
                total_return_pct=14.2,
                max_drawdown_pct=-8.4,
                annualized_return_pct=14.2,
                sharpe_ratio=0.63,
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        result = await agent._execute_tool("get_metrics", {"symbol": "AAPL", "range_key": "1y"})

        assert result["success"] is True
        assert result["data"]["total_return_pct"] == 14.2

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
    async def test_run_with_knowledge_query(self, agent):
        agent.rag_pipeline.search = AsyncMock(
            return_value=type(
                "KnowledgeMock",
                (),
                {
                    "documents": [type("Doc", (), {"content": "市盈率是估值指标。", "source": "valuation_metrics.md", "score": 0.9})()],
                    "model_dump": lambda self: {
                        "documents": [{"content": "市盈率是估值指标。", "source": "valuation_metrics.md", "score": 0.9}],
                        "total_found": 1,
                    },
                },
            )()
        )
        agent.confidence_scorer.calculate.return_value = 0.9
        agent.confidence_scorer.get_confidence_level.return_value = "high"

        events = [event async for event in agent.run("什么是市盈率")]

        assert any(event.type == "model_selected" for event in events)
        assert any(event.type == "tool_start" for event in events)
        assert any(event.type == "chunk" for event in events)
        done = next(event for event in events if event.type == "done")
        assert done.data["confidence"]["level"] in {"high", "medium", "low"}

    @pytest.mark.asyncio
    async def test_run_with_tool_results(self, agent):
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

        events = [event async for event in agent.run("AAPL价格")]

        assert any(event.type == "tool_start" for event in events)
        assert any(event.type == "tool_data" for event in events)
        assert any(event.type == "done" for event in events)

    @pytest.mark.asyncio
    async def test_run_done_payload_contract(self, agent):
        route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="AAPL price",
            symbols=["AAPL"],
            requires_price=True,
        )
        complexity = ComplexityScore(
            level="simple",
            score=0.2,
            recommended_model="deepseek-chat",
            rag_top_k=3,
            timeout_multiplier=1.0,
            reasoning="Simple query with minimal requirements",
        )
        agent.route_planner.analyze = AsyncMock(return_value=(route, complexity))
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
        agent.data_validator.validate_tool_results = Mock(
            return_value={
                "confidence": 80,
                "level": "high",
                "missing": [],
                "can_analyze": True,
            }
        )
        agent.data_validator.should_block_response = Mock(return_value=False)
        agent.response_generator = None

        events = [event async for event in agent.run("AAPL price")]
        done = next(event for event in events if event.type == "done")

        assert {
            "blocks",
            "route",
            "llm_used",
            "disclaimer",
            "rag_citations",
            "tool_latencies",
            "query_complexity",
        }.issubset(done.data.keys())
        assert done.data["route"] == {"type": "market", "symbols": ["AAPL"], "range_key": None}
        assert isinstance(done.data["tool_latencies"], list)
        assert done.data["query_complexity"]["rag_top_k"] == 3

    @pytest.mark.asyncio
    async def test_run_with_advice_refusal(self, agent):
        events = [event async for event in agent.run("AAPL 现在可以买入吗")]
        assert any(event.type == "chunk" for event in events)
        done = next(event for event in events if event.type == "done")
        assert done.verified is True
        assert done.data["blocks"][0]["type"] == "warning"

    @pytest.mark.asyncio
    async def test_compose_technical_analysis_blocks(self, agent):
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
        points = [
            PricePoint(date=f"2024-03-{idx:02d}", open=100 + idx, high=101 + idx, low=99 + idx, close=100 + idx, volume=1000 + idx)
            for idx in range(1, 31)
        ]
        agent.market_service.get_history = AsyncMock(
            return_value=HistoryData(
                symbol="AAPL",
                days=30,
                range_key="1m",
                data=points,
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )
        agent.market_service.get_metrics = AsyncMock(
            return_value=RiskMetrics(
                symbol="AAPL",
                range_key="1y",
                annualized_volatility=18.2,
                total_return_pct=12.5,
                max_drawdown_pct=-6.3,
                annualized_return_pct=12.5,
                sharpe_ratio=0.69,
                source="yfinance",
                timestamp="2024-03-05T10:00:00",
            )
        )

        events = [event async for event in agent.run("AAPL 波动率和最大回撤")]
        done = next(event for event in events if event.type == "done")
        block_types = [block["type"] for block in done.data["blocks"]]
        assert "table" in block_types
        assert "chart" in block_types
