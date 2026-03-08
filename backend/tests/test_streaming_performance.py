import pytest
import time
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.agent.core import AgentCore


async def mock_stream_generator():
    """Mock async generator for streaming response."""
    # Simulate streaming chunks
    await asyncio.sleep(0.1)  # Simulate some delay

    # Yield some text deltas
    for text in ["This ", "is ", "a ", "test ", "response"]:
        delta = Mock()
        delta.type = "text_delta"
        delta.text = text

        event = Mock()
        event.type = "content_block_delta"
        event.delta = delta

        yield event


@pytest.mark.asyncio
async def test_first_byte_latency():
    """Test that first response chunk arrives quickly."""

    with patch('app.agent.core.MarketDataService') as MockMarket, \
         patch('app.agent.core.HybridRAGPipeline') as MockRAG, \
         patch('app.agent.core.WebSearchService') as MockSearch, \
         patch('app.agent.core.ConfidenceScorer') as MockScorer, \
         patch('app.agent.core.QueryRouter') as MockRouter, \
         patch('app.agent.core.ModelAdapterFactory') as MockAdapterFactory:

        # Setup mocks
        mock_market = MockMarket.return_value
        mock_market.get_price = AsyncMock(return_value=Mock(
            symbol="AAPL",
            price=150.0,
            currency="USD",
            source="yfinance",
            timestamp="2024-03-05T10:00:00",
            change_percent=2.5,
            model_dump=lambda: {
                'symbol': 'AAPL',
                'price': 150.0,
                'currency': 'USD',
                'source': 'yfinance',
                'timestamp': '2024-03-05T10:00:00',
                'change_percent': 2.5
            }
        ))

        mock_search = MockSearch.return_value
        mock_rag = MockRAG.return_value
        mock_scorer = MockScorer.return_value

        # Mock the router to return a market query route
        mock_router = MockRouter.return_value
        mock_route = Mock()
        mock_route.query_type = Mock(name='MARKET')
        mock_route.symbols = ['AAPL']
        mock_route.requires_price = True
        mock_route.requires_change = False
        mock_route.requires_history = False
        mock_route.requires_info = False
        mock_route.days = None
        mock_route.cleaned_query = "AAPL股价"
        mock_router.classify_async = AsyncMock(return_value=mock_route)

        # Mock the adapter
        mock_adapter = Mock()
        mock_adapter.create_message_stream = Mock(return_value=mock_stream_generator())
        MockAdapterFactory.create_adapter = Mock(return_value=mock_adapter)

        agent = AgentCore()
        query = "AAPL股价"

        start_time = time.time()
        first_chunk_time = None
        events_seen = []

        async for event in agent.run(query):
            events_seen.append(event.type)
            print(f"Event: {event.type}, Time: {time.time() - start_time:.2f}s")
            if event.type == "error":
                print(f"Error message: {getattr(event, 'message', 'No message')}")
                print(f"Error code: {getattr(event, 'code', 'No code')}")
            if event.type == "chunk" and event.text and first_chunk_time is None:
                first_chunk_time = time.time() - start_time
                print(f"First chunk text: {event.text[:100]}")
                break

        print(f"All events seen: {events_seen}")
        assert first_chunk_time is not None, f"No chunk event received. Events: {events_seen}"
        assert first_chunk_time < 0.5, f"First byte took {first_chunk_time:.2f}s, expected < 0.5s"
