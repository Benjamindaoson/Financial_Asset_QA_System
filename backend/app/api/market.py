"""Market overview and analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.market import MarketDataService


router = APIRouter()
market_service = MarketDataService()


@router.get("/market-overview")
async def get_market_overview():
    """Return live market overview cards and summary."""

    return await market_service.get_market_overview()


@router.get("/metrics/{symbol}")
async def get_metrics(symbol: str, range_key: str = Query("1y", pattern="^(1m|3m|6m|ytd|1y|5y)$")):
    """Return return/risk metrics for a symbol."""

    metrics = await market_service.get_metrics(symbol, range_key=range_key)
    if metrics.error:
        raise HTTPException(status_code=404, detail=metrics.error)
    return metrics


@router.get("/compare")
async def compare_assets(symbols: str, range_key: str = Query("1y", pattern="^(1m|3m|6m|ytd|1y|5y)$")):
    """Return comparison table and normalized chart for multiple symbols."""

    parsed = [item.strip() for item in symbols.split(",") if item.strip()]
    if len(parsed) < 2:
        raise HTTPException(status_code=422, detail="at least two symbols are required")

    return await market_service.compare_assets(parsed, range_key=range_key)
