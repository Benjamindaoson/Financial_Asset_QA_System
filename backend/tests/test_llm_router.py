"""Tests for LLMRouter."""

import pytest
import json
from unittest.mock import AsyncMock, patch
from app.routing.llm_router import LLMRouter


@pytest.mark.asyncio
async def test_llm_router_initialization():
    """Test that LLMRouter initializes correctly."""
    router = LLMRouter()

    assert router is not None
    assert router.prompt_manager is not None
    assert router.llm_client is not None


@pytest.mark.asyncio
async def test_route_simple_price_query():
    """Test routing a simple price query."""
    router = LLMRouter()

    with patch.object(router.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_response = json.dumps({
            "question_type": "real_time_quote",
            "confidence": 0.95,
            "route": "api_direct",
            "entities": {
                "ticker": "AAPL",
                "company": "Apple",
                "time_range": "today"
            },
            "reasoning": "明确询问实时价格变动"
        })
        mock_llm.return_value = mock_response

        result = await router.route("AAPL今天涨了多少？")

        assert result["question_type"] == "real_time_quote"
        assert result["confidence"] == 0.95
        assert result["route"] == "api_direct"
        assert result["entities"]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_route_knowledge_query():
    """Test routing a financial knowledge query."""
    router = LLMRouter()

    with patch.object(router.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_response = json.dumps({
            "question_type": "financial_knowledge",
            "confidence": 0.98,
            "route": "rag_retrieval",
            "entities": {
                "ticker": None,
                "company": None,
                "time_range": None
            },
            "reasoning": "询问金融概念定义"
        })
        mock_llm.return_value = mock_response

        result = await router.route("什么是市盈率？")

        assert result["question_type"] == "financial_knowledge"
        assert result["route"] == "rag_retrieval"


@pytest.mark.asyncio
async def test_route_company_analysis():
    """Test routing a company analysis query."""
    router = LLMRouter()

    with patch.object(router.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_response = json.dumps({
            "question_type": "company_analysis",
            "confidence": 0.92,
            "route": "hybrid",
            "entities": {
                "ticker": "TSLA",
                "company": "Tesla",
                "time_range": "today"
            },
            "reasoning": "需要结合实时数据和新闻事件分析"
        })
        mock_llm.return_value = mock_response

        result = await router.route("为什么特斯拉今天暴涨？")

        assert result["question_type"] == "company_analysis"
        assert result["route"] == "hybrid"
        assert result["entities"]["ticker"] == "TSLA"


@pytest.mark.asyncio
async def test_route_uses_correct_temperature():
    """Test that router uses correct temperature from config."""
    router = LLMRouter()

    with patch.object(router.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_response = json.dumps({
            "question_type": "real_time_quote",
            "confidence": 0.95,
            "route": "api_direct",
            "entities": {"ticker": "AAPL", "company": "Apple", "time_range": "today"},
            "reasoning": "test"
        })
        mock_llm.return_value = mock_response

        await router.route("Test query")

        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs['temperature'] == 0.0  # Router should use 0.0


@pytest.mark.asyncio
async def test_route_invalid_json_response():
    """Test handling of invalid JSON response from LLM."""
    router = LLMRouter()

    with patch.object(router.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "This is not valid JSON"

        with pytest.raises(json.JSONDecodeError):
            await router.route("Test query")


@pytest.mark.asyncio
async def test_route_missing_required_fields():
    """Test handling of response missing required fields."""
    router = LLMRouter()

    with patch.object(router.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_response = json.dumps({
            "question_type": "real_time_quote"
            # Missing confidence, route, entities, reasoning
        })
        mock_llm.return_value = mock_response

        with pytest.raises(KeyError):
            await router.route("Test query")
