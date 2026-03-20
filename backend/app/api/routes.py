"""API routes for chat, health checks, and chart data."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.agent import AgentCore
from app.api.market import router as market_router
from app.config import settings
from app.enricher import QueryEnricher
from app.market import MarketDataService
from app.models import ChartResponse, ChatRequest, HealthResponse
from app.session.memory import SessionMemory, ConversationTurn


router = APIRouter()
router.include_router(market_router)

agent = AgentCore()
enricher = QueryEnricher()
market_service = MarketDataService()
session_memory = SessionMemory()


@router.post("/chat")
async def chat(request: ChatRequest, model: Optional[str] = None):
    """Chat endpoint with SSE streaming and multi-turn conversation support."""

    # Get session_id from request or generate new one
    session_id = request.session_id or f"session_{int(datetime.utcnow().timestamp())}"

    # Get conversation context for reference resolution
    context = await session_memory.get_context(session_id, max_turns=5)

    # Resolve references (e.g., "它" -> "AAPL")
    resolved_query = session_memory.resolve_references(request.query, context)

    # Enrich query
    enriched_query = enricher.enrich(resolved_query)

    async def event_generator():
        assistant_response = ""
        symbols_mentioned = []
        tools_used = []

        try:
            async for event in agent.run(enriched_query, model_name=model):
                # Collect assistant response for session storage
                if event.type == "chunk" or event.type == "analysis_chunk":
                    if hasattr(event, 'text') and event.text:
                        assistant_response += event.text

                # Track tools used
                if event.type == "tool_start" and hasattr(event, 'name'):
                    tools_used.append(event.name)

                # Extract symbols from route
                if event.type == "blocks" and hasattr(event, 'data'):
                    route_data = event.data.get('route', {})
                    if route_data.get('symbols'):
                        symbols_mentioned.extend(route_data['symbols'])

                yield {
                    "event": "message",
                    "data": json.dumps(event.model_dump(exclude_none=True), ensure_ascii=False),
                }

            # Save conversation turn after completion
            if assistant_response or symbols_mentioned:
                # Save user turn
                user_turn = ConversationTurn(
                    role="user",
                    content=request.query,
                    timestamp=datetime.utcnow().isoformat(),
                    tools_used=None,
                    symbols_mentioned=symbols_mentioned if symbols_mentioned else None
                )
                await session_memory.save_turn(session_id, None, user_turn)

                # Save assistant turn
                assistant_turn = ConversationTurn(
                    role="assistant",
                    content=assistant_response[:500] if assistant_response else "Response generated",
                    timestamp=datetime.utcnow().isoformat(),
                    tools_used=tools_used if tools_used else None,
                    symbols_mentioned=symbols_mentioned if symbols_mentioned else None
                )
                await session_memory.save_turn(session_id, None, assistant_turn)

        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(exc), "code": "STREAM_ERROR"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.get("/models")
async def list_models():
    """List available models."""

    return {"models": agent.get_available_models(), "usage": agent.get_usage_report()}


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
        if hasattr(agent, "rag_pipeline") and agent.rag_pipeline:
            count = agent.rag_pipeline.get_collection_count()
            components["chromadb"] = f"ready ({count} docs)" if count > 0 else "empty"
            components["rag_token_match"] = "ready"
        else:
            components["chromadb"] = "unavailable"
            components["rag_token_match"] = "unavailable"
    except Exception as e:
        components["chromadb"] = f"error: {str(e)[:50]}"
        components["rag_token_match"] = "ready"  # token-match 仍可用

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
