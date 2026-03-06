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


@router.post("/chat")
async def chat(request: ChatRequest, model: Optional[str] = None):
    """
    Chat endpoint with SSE streaming

    Args:
        request: Chat request with query
        model: Optional model name to use (e.g., "claude-opus", "deepseek-chat")

    Returns: text/event-stream
    """
    # Enrich query with hints
    enriched_query = enricher.enrich(request.query)

    async def event_generator():
        """Generate SSE events"""
        try:
            async for event in agent.run(enriched_query, model_name=model):
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


@router.get("/models")
async def list_models():
    """
    List available models
    """
    return {
        "models": agent.get_available_models(),
        "usage": agent.get_usage_report()
    }


@router.get("/health")
async def health() -> HealthResponse:
    """
    Health check endpoint
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


@router.get("/chart/{symbol}")
async def get_chart(symbol: str, days: int = 30) -> ChartResponse:
    """
    Get historical chart data for a symbol
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
