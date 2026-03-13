"""Tests for HybridRouter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.routing.hybrid_router import HybridRouter
from app.routing.router import QueryRouter


@pytest.mark.asyncio
async def test_hybrid_router_initialization():
    """Test that HybridRouter initializes correctly."""
    router = HybridRouter()

    assert router is not None
    assert router.rule_router is not None
    assert router.llm_router is not None
    assert router.confidence_threshold == 0.8


@pytest.mark.asyncio
async def test_high_confidence_uses_rule_router():
    """Test that high confidence queries use rule router only."""
    router = HybridRouter()

    with patch.object(router.rule_router, 'classify') as mock_rule:
        from app.routing.router import QueryRoute, QueryType

        mock_route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="AAPL今天涨了多少？",
            symbols=["AAPL"],
            requires_price=True
        )
        mock_rule.return_value = mock_route

        result = await router.route("AAPL今天涨了多少？")

        # Should use rule router result
        assert result["route"] == "api_direct"
        assert result["confidence"] >= 0.7  # Reasonably high confidence


@pytest.mark.asyncio
async def test_low_confidence_calls_llm_router():
    """Test that low confidence queries call LLM router."""
    router = HybridRouter()

    with patch.object(router.rule_router, 'classify') as mock_rule, \
         patch.object(router.llm_router, 'route', new_callable=AsyncMock) as mock_llm:

        from app.routing.router import QueryRoute, QueryType

        mock_route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="为什么特斯拉今天暴涨？",
            symbols=["TSLA"],
            requires_price=True
        )
        mock_rule.return_value = mock_route

        mock_llm.return_value = {
            "question_type": "company_analysis",
            "confidence": 0.92,
            "route": "hybrid",
            "entities": {"ticker": "TSLA", "company": "Tesla", "time_range": "today"},
            "reasoning": "需要结合实时数据和新闻事件分析"
        }

        result = await router.route("为什么特斯拉今天暴涨？")

        # Should call LLM router
        mock_llm.assert_called_once()
        # Should use LLM result
        assert result["route"] == "hybrid"
        assert result["confidence"] == 0.92


@pytest.mark.asyncio
async def test_llm_failure_fallback_to_rule():
    """Test fallback to rule router when LLM fails."""
    router = HybridRouter()

    with patch.object(router.rule_router, 'classify') as mock_rule, \
         patch.object(router.llm_router, 'route', new_callable=AsyncMock) as mock_llm:

        from app.routing.router import QueryRoute, QueryType

        mock_route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="Test query",
            symbols=["AAPL"],
            requires_price=True
        )
        mock_rule.return_value = mock_route

        # LLM fails
        mock_llm.side_effect = Exception("LLM API Error")

        result = await router.route("Test query")

        # Should fallback to rule router result
        assert result["route"] == "api_direct"
        assert "confidence" in result


@pytest.mark.asyncio
async def test_merge_entities():
    """Test merging entities from rule and LLM routers."""
    router = HybridRouter()

    with patch.object(router.rule_router, 'classify') as mock_rule, \
         patch.object(router.llm_router, 'route', new_callable=AsyncMock) as mock_llm:

        from app.routing.router import QueryRoute, QueryType

        mock_route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="AAPL今天涨了多少？",
            symbols=["AAPL"],
            requires_price=True
        )
        mock_rule.return_value = mock_route

        mock_llm.return_value = {
            "question_type": "real_time_quote",
            "confidence": 0.95,
            "route": "api_direct",
            "entities": {"ticker": "AAPL", "company": "Apple", "time_range": "today"},
            "reasoning": "明确询问实时价格"
        }

        result = await router.route("AAPL今天涨了多少？")

        # Should merge entities
        assert result["entities"]["ticker"] == "AAPL"
        assert result["entities"]["company"] == "Apple"
        assert result["entities"]["time_range"] == "today"


@pytest.mark.asyncio
async def test_calculate_confidence():
    """Test confidence calculation."""
    router = HybridRouter()

    # Test high confidence case
    confidence = router._calculate_confidence(
        query="AAPL今天涨了多少？",
        entities={"ticker": "AAPL", "time_range": "today"}
    )
    assert confidence > 0.8

    # Test low confidence case
    confidence = router._calculate_confidence(
        query="为什么特斯拉今天暴涨？",
        entities={"ticker": "TSLA"}
    )
    assert confidence < 0.8


@pytest.mark.asyncio
async def test_disabled_hybrid_routing():
    """Test behavior when hybrid routing is disabled."""
    with patch('app.config.settings.HYBRID_ROUTING_ENABLED', False):
        router = HybridRouter()

        with patch.object(router.rule_router, 'classify') as mock_rule:
            from app.routing.router import QueryRoute, QueryType

            mock_route = QueryRoute(
                query_type=QueryType.MARKET,
                cleaned_query="Test query",
                symbols=["AAPL"],
                requires_price=True
            )
            mock_rule.return_value = mock_route

            result = await router.route("Test query")

            # Should only use rule router
            assert result["route"] == "api_direct"
