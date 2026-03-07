"""
API Routes - FastAPI endpoints with SSE streaming
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json
from datetime import datetime
from typing import Optional
from app.models import ChatRequest, HealthResponse, ChartResponse
from app.agent import AgentCore
from app.enricher import QueryEnricher
from app.market import MarketDataService
from app.config import settings

router = APIRouter()

# Initialize services
agent = AgentCore()
enricher = QueryEnricher()
market_service = MarketDataService()


@router.post("/chat", tags=["chat"])
async def chat(request: ChatRequest, model: Optional[str] = None):
    """
    Chat endpoint with Server-Sent Events (SSE) streaming

    This endpoint processes natural language queries about financial assets and returns
    streaming responses with real-time analysis steps.

    **Request Body:**
    - `query` (string, required): User's question about stocks, funds, or financial concepts
    - `session_id` (string, optional): Session ID for multi-turn conversations

    **Query Parameters:**
    - `model` (string, optional): Model to use (e.g., "claude-opus", "deepseek-chat")

    **Response Format (SSE):**
    The response is a stream of events with the following types:
    - `model_selected`: Indicates which AI model was selected
    - `tool_start`: Agent is using a tool (e.g., market data lookup)
    - `tool_data`: Data retrieved from tool execution
    - `chunk`: Streaming text chunk from AI response
    - `done`: Final event with sources and metadata
    - `error`: Error occurred during processing

    **Example Query:**
    ```
    {
      "query": "苹果股票今天涨了多少？",
      "session_id": "session_123"
    }
    ```

    **Returns:**
    - Content-Type: text/event-stream
    - Events containing analysis steps and AI response
    """
    # Enrich query with hints
    enriched_query = enricher.enrich(request.query)

    async def event_generator():
        """Generate SSE events"""
        try:
            async for event in agent.run(enriched_query, model_name=model, session_id=request.session_id):
                # Convert event to SSE format
                event_data = event.model_dump(exclude_none=True)
                yield {
                    "event": "message",
                    "data": json.dumps(event_data, ensure_ascii=False)
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "message": str(e),
                    "code": "STREAM_ERROR"
                })
            }

    return EventSourceResponse(event_generator())


@router.get("/models", tags=["chat"])
async def list_models():
    """
    List available AI models and usage statistics

    Returns information about available models and their usage patterns.

    **Returns:**
    - `models`: List of available model names
    - `usage`: Usage statistics for each model

    **Example Response:**
    ```json
    {
      "models": ["claude-sonnet-4", "claude-opus-4", "deepseek-chat"],
      "usage": {
        "claude-sonnet-4": {"count": 150, "avg_tokens": 1200}
      }
    }
    ```
    """
    return {
        "models": agent.get_available_models(),
        "usage": agent.get_usage_report()
    }


@router.get("/health", tags=["health"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Health check endpoint for monitoring system status

    Checks the status of all critical system components including:
    - Redis cache connection
    - ChromaDB vector database
    - API key configurations (Claude, Alpha Vantage, Tavily)
    - Market data service availability

    **Returns:**
    - `status`: Overall system status ("healthy", "degraded", or "unhealthy")
    - `version`: API version
    - `timestamp`: Current UTC timestamp
    - `components`: Status of individual components

    **Status Values:**
    - `healthy`: All critical components operational
    - `degraded`: Some non-critical components unavailable
    - `unhealthy`: Critical components down

    **Example Response:**
    ```json
    {
      "status": "healthy",
      "version": "1.0.0",
      "timestamp": "2026-03-07T12:00:00",
      "components": {
        "redis": "connected",
        "chromadb": "ready",
        "claude_api": "configured"
      }
    }
    ```
    """
    components = {}

    # Check Redis
    try:
        market_service.redis_client.ping()
        components["redis"] = "connected"
    except Exception:
        components["redis"] = "disconnected"

    # Check ChromaDB
    try:
        agent.rag_pipeline.get_collection_count()
        components["chromadb"] = "ready"
    except Exception:
        components["chromadb"] = "unavailable"

    # Check model configuration
    components["claude_api"] = "configured" if settings.ANTHROPIC_API_KEY else "not_configured"
    components["alpha_vantage"] = "configured" if settings.ALPHA_VANTAGE_API_KEY else "not_configured"
    components["tavily"] = "configured" if settings.TAVILY_API_KEY else "not_configured"

    # Library-level probe
    components["yfinance"] = "available" if hasattr(market_service, "_fetch_yfinance_info") else "unavailable"

    # Determine overall status
    critical_down = components["redis"] == "disconnected" or components["claude_api"] == "not_configured"
    status = "degraded" if critical_down else "healthy"

    return HealthResponse(
        status=status,
        version=settings.__version__ if hasattr(settings, '__version__') else "1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        components=components
    )


@router.get("/chart/{symbol}", tags=["market"], response_model=ChartResponse)
async def get_chart(symbol: str, days: int = 30) -> ChartResponse:
    """
    Get historical chart data for a stock symbol

    Retrieves historical price data for the specified stock symbol over the given time period.
    Data is cached in Redis for performance.

    **Path Parameters:**
    - `symbol` (string, required): Stock ticker symbol (e.g., "AAPL", "TSLA", "BABA")

    **Query Parameters:**
    - `days` (integer, optional): Number of days of historical data (7-365, default: 30)

    **Returns:**
    - `symbol`: Stock ticker symbol
    - `data`: Array of price data points with date, open, high, low, close, volume
    - `source`: Data source (e.g., "yfinance", "cache")

    **Example Request:**
    ```
    GET /api/chart/AAPL?days=30
    ```

    **Example Response:**
    ```json
    {
      "symbol": "AAPL",
      "data": [
        {
          "date": "2026-03-01",
          "open": 150.0,
          "high": 152.5,
          "low": 149.0,
          "close": 151.0,
          "volume": 50000000
        }
      ],
      "source": "yfinance"
    }
    ```

    **Errors:**
    - 422: Invalid days parameter (must be 7-365)
    - 404: No data available for symbol
    """
    if days < 7 or days > 365:
        raise HTTPException(status_code=422, detail="days must be between 7 and 365")

    history = await market_service.get_history(symbol, days)

    if not history.data:
        raise HTTPException(status_code=404, detail="No data available for symbol")

    return ChartResponse(
        symbol=history.symbol,
        data=history.data,
        source=history.source
    )


@router.get("/quote/{symbol}", tags=["market"])
async def get_quote(symbol: str):
    """
    Get real-time quote for a stock symbol

    Retrieves current price and basic information for the specified stock symbol.
    Data is cached for 60 seconds to reduce API calls.

    **Path Parameters:**
    - `symbol` (string, required): Stock ticker symbol (e.g., "AAPL", "TSLA", "BABA")

    **Returns:**
    - `symbol`: Normalized stock ticker symbol
    - `price`: Current price
    - `currency`: Currency code (e.g., "USD", "CNY")
    - `name`: Company name
    - `source`: Data source (e.g., "yfinance", "alpha_vantage")
    - `timestamp`: Data timestamp

    **Example Request:**
    ```
    GET /api/quote/AAPL
    ```

    **Example Response:**
    ```json
    {
      "symbol": "AAPL",
      "price": 151.25,
      "currency": "USD",
      "name": "Apple Inc.",
      "source": "yfinance",
      "timestamp": "2026-03-07T12:00:00"
    }
    ```

    **Errors:**
    - 404: Symbol not found or data unavailable
    """
    result = await market_service.get_price(symbol)

    if result.error or not result.price:
        raise HTTPException(status_code=404, detail=result.error or "Symbol not found")

    return result
