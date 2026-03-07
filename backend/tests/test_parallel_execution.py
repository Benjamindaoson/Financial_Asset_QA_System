"""Test parallel tool execution performance."""

import pytest
import time
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.agent.core import AgentCore


@pytest.mark.asyncio
async def test_execute_tools_parallel():
    """Test that _execute_tools_parallel executes tools concurrently."""

    execution_log = []

    async def mock_get_price(symbol):
        execution_log.append(('get_price', 'start', time.time()))
        await asyncio.sleep(1.0)
        execution_log.append(('get_price', 'end', time.time()))
        return Mock(
            symbol=symbol,
            price=150.0,
            currency="USD",
            source="yfinance",
            timestamp="2024-03-05T10:00:00",
            model_dump=lambda: {
                'symbol': symbol,
                'price': 150.0,
                'currency': 'USD',
                'source': 'yfinance',
                'timestamp': '2024-03-05T10:00:00'
            }
        )

    async def mock_get_history(symbol, days):
        execution_log.append(('get_history', 'start', time.time()))
        await asyncio.sleep(0.8)
        execution_log.append(('get_history', 'end', time.time()))
        return Mock(
            symbol=symbol,
            days=days,
            data=[],
            source="yfinance",
            timestamp="2024-03-05T10:00:00",
            model_dump=lambda: {
                'symbol': symbol,
                'days': days,
                'data': [],
                'source': 'yfinance',
                'timestamp': '2024-03-05T10:00:00'
            }
        )

    async def mock_search_web(query):
        execution_log.append(('search_web', 'start', time.time()))
        await asyncio.sleep(1.2)
        execution_log.append(('search_web', 'end', time.time()))
        return Mock(
            results=[],
            total_found=0,
            source="web",
            timestamp="2024-03-05T10:00:00",
            model_dump=lambda: {
                'results': [],
                'total_found': 0,
                'source': 'web',
                'timestamp': '2024-03-05T10:00:00'
            }
        )

    with patch('app.agent.core.MarketDataService') as MockMarket, \
         patch('app.agent.core.HybridRAGPipeline') as MockRAG, \
         patch('app.agent.core.WebSearchService') as MockSearch, \
         patch('app.agent.core.ConfidenceScorer') as MockScorer, \
         patch('app.agent.core.QueryRouter') as MockRouter:

        # Setup mocks
        mock_market = MockMarket.return_value
        mock_market.get_price = AsyncMock(side_effect=mock_get_price)
        mock_market.get_history = AsyncMock(side_effect=mock_get_history)

        mock_search = MockSearch.return_value
        mock_search.search = AsyncMock(side_effect=mock_search_web)

        mock_rag = MockRAG.return_value
        mock_scorer = MockScorer.return_value
        mock_router = MockRouter.return_value

        agent = AgentCore()

        # Create a tool plan with 3 tools
        tool_plan = [
            {"name": "get_price", "params": {"symbol": "AAPL"}, "display": "Getting price..."},
            {"name": "get_history", "params": {"symbol": "AAPL", "days": 30}, "display": "Getting history..."},
            {"name": "search_web", "params": {"query": "AAPL news"}, "display": "Searching web..."},
        ]

        start_time = time.time()
        results = await agent._execute_tools_parallel(tool_plan)
        elapsed = time.time() - start_time

        # Verify all tools executed
        assert len(results) == 3
        assert all(r["success"] for r in results)

        # Print execution log
        print(f"\nExecution log:")
        base_time = execution_log[0][2] if execution_log else 0
        for entry in execution_log:
            print(f"  {entry[0]:15} {entry[1]:5} at {entry[2] - base_time:.3f}s")
        print(f"\nTotal elapsed time: {elapsed:.2f}s")

        # Check that tools ran in parallel
        # Sequential would be: 1.0 + 0.8 + 1.2 = 3.0s
        # Parallel should be: max(1.0, 0.8, 1.2) = 1.2s
        # Allow some overhead, so check < 2.0s
        assert elapsed < 2.0, f"Expected parallel execution < 2s, got {elapsed:.2f}s"

        # Verify tools started around the same time (within 0.1s)
        start_times = [entry[2] for entry in execution_log if entry[1] == 'start']
        if len(start_times) >= 2:
            time_spread = max(start_times) - min(start_times)
            assert time_spread < 0.2, f"Tools should start concurrently, but spread was {time_spread:.3f}s"
