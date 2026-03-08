"""API routes for chat, health checks, and chart data."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.agent import AgentCore
from app.config import settings
from app.enricher import QueryEnricher
from app.market import MarketDataService
from app.models import ChartResponse, ChatRequest, HealthResponse

router = APIRouter()

agent = AgentCore()
enricher = QueryEnricher()
market_service = MarketDataService()


@router.post("/chat")
async def chat(request: ChatRequest, model: Optional[str] = None):
    """Chat endpoint with SSE streaming."""

    enriched_query = enricher.enrich(request.query)

    async def event_generator():
        try:
            async for event in agent.run(enriched_query, model_name=model):
                yield {
                    "event": "message",
                    "data": json.dumps(event.model_dump(exclude_none=True), ensure_ascii=False),
                }
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "type": "error",
                        "message": str(exc),
                        "code": "STREAM_ERROR",
                    }
                ),
            }

    return EventSourceResponse(event_generator())


@router.get("/models")
async def list_models():
    """List available models."""

    return {
        "models": agent.get_available_models(),
        "usage": agent.get_usage_report(),
    }


@router.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint."""

    components = {}

    try:
        market_service.redis_client.ping()
        components["redis"] = "connected"
    except Exception:
        components["redis"] = "disconnected"

    try:
        agent.rag_pipeline.get_collection_count()
        components["chromadb"] = "ready"
    except Exception:
        components["chromadb"] = "unavailable"

    components["deepseek_api"] = "configured" if settings.DEEPSEEK_API_KEY else "not_configured"
    components["alpha_vantage"] = "configured" if settings.ALPHA_VANTAGE_API_KEY else "not_configured"
    components["tavily"] = "configured" if settings.TAVILY_API_KEY else "not_configured"
    components["yfinance"] = "available" if hasattr(market_service, "_fetch_yfinance_info") else "unavailable"

    critical_down = components["redis"] == "disconnected" or components["deepseek_api"] == "not_configured"
    status = "degraded" if critical_down else "healthy"

    return HealthResponse(
        status=status,
        version=settings.__version__ if hasattr(settings, "__version__") else "1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        components=components,
    )


@router.get("/chart/{symbol}")
async def get_chart(symbol: str, days: int = 30) -> ChartResponse:
    """Return historical chart data for a symbol."""

    if days < 7 or days > 365:
        raise HTTPException(status_code=422, detail="days must be between 7 and 365")

    history = await market_service.get_history(symbol, days)
    if not history.data:
        raise HTTPException(status_code=404, detail="No data available for symbol")

    return ChartResponse(symbol=history.symbol, data=history.data, source=history.source)
