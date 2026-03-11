"""API routes for chat, health checks, and chart data."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.agent import AgentCore
from app.api.market import router as market_router
from app.api.feedback import router as feedback_router
from app.api.monitoring import router as monitoring_router
from app.api.auth import router as auth_router
from app.api.session import router as session_router
# from app.api.enhanced_routes import router as enhanced_router  # Disabled due to missing dependencies
from app.config import settings
from app.enricher import QueryEnricher
from app.market import MarketDataService
from app.models import ChartResponse, ChatRequest, HealthResponse


router = APIRouter()
router.include_router(market_router)
router.include_router(feedback_router)
router.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
router.include_router(auth_router, tags=["auth"])
router.include_router(session_router, tags=["sessions"])
# router.include_router(enhanced_router, tags=["enhanced"])  # Disabled due to missing dependencies

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
                "data": json.dumps({"type": "error", "message": str(exc), "code": "STREAM_ERROR"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.get("/models")
async def list_models():
    """List available models."""

    models = agent.get_available_models()
    if models and models[0].get("id") == "degraded-local":
        return models
    return {"models": models, "usage": agent.get_usage_report()}


@router.get("/rag/status")
async def rag_status():
    """Return current RAG corpus and index status."""

    status = agent.rag_pipeline.get_status()
    status["timestamp"] = datetime.utcnow().isoformat()
    return status


@router.get("/rag/search")
async def rag_search(query: str = Query(..., min_length=1, max_length=300)):
    """Debug endpoint for retrieval-only RAG inspection."""

    result = await agent.rag_pipeline.search(query, use_hybrid=True)
    payload = result.model_dump()
    payload["status"] = agent.rag_pipeline.get_status()
    return payload


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
    components["yfinance"] = "available"
    critical_down = components["deepseek_api"] == "not_configured" or components["redis"] == "disconnected"
    return HealthResponse(
        status="degraded" if critical_down else "healthy",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        components=components,
        reason="llm_not_configured" if components["deepseek_api"] == "not_configured" else None,
        available_features=["market_data", "rag_retrieval"] if components["deepseek_api"] == "not_configured" else None,
    )


@router.get("/chart/{symbol}")
async def get_chart(
    symbol: str,
    days: int = Query(30, ge=7, le=365),
    range_key: Optional[str] = Query(None, pattern="^(1m|3m|6m|ytd|1y|5y)$"),
) -> ChartResponse:
    """Return historical chart data for a symbol."""

    history = await market_service.get_history(symbol, days=days, range_key=range_key)
    if not history.data:
        raise HTTPException(status_code=404, detail="No data available for symbol")

    return ChartResponse(symbol=history.symbol, data=history.data, source=history.source, range_key=history.range_key)
