"""Routing and tool-planning helpers for the agent runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.routing import QueryRoute, QueryRouter, QueryType
from app.routing.complexity_analyzer import ComplexityScore, QueryComplexityAnalyzer


class RoutePlanner:
    """Plan query execution without coupling routing logic to the agent core."""

    def __init__(
        self,
        query_router: QueryRouter,
        complexity_analyzer: QueryComplexityAnalyzer,
    ) -> None:
        self.query_router = query_router
        self.complexity_analyzer = complexity_analyzer

    async def analyze(self, query: str) -> Tuple[QueryRoute, ComplexityScore]:
        route = await self.query_router.classify_async(query)
        complexity = self.complexity_analyzer.analyze(query, route)
        return route, complexity

    async def build_tool_plan(
        self,
        route: QueryRoute,
        rag_top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        plan: List[Dict[str, Any]] = []

        def add_tool(name: str, params: Dict[str, Any], display: str) -> None:
            plan.append({"name": name, "params": params, "display": display})

        primary_symbol = route.symbols[0] if route.symbols else None
        days = route.days or 30
        range_key = route.range_key

        if route.requires_comparison and len(route.symbols) >= 2:
            add_tool(
                "compare_assets",
                {"symbols": route.symbols[:4], "range_key": range_key or "1y"},
                f"Comparing {', '.join(route.symbols[:4])}...",
            )
            return plan

        if route.query_type in {QueryType.MARKET, QueryType.HYBRID} and primary_symbol:
            if route.requires_price:
                add_tool(
                    "get_price",
                    {"symbol": primary_symbol},
                    f"Fetching latest price for {primary_symbol}...",
                )
                if not route.requires_change:
                    add_tool(
                        "get_change",
                        {"symbol": primary_symbol, "days": 7, "range_key": None},
                        f"Fetching 7-day change for {primary_symbol}...",
                    )
            if route.requires_change:
                add_tool(
                    "get_change",
                    {"symbol": primary_symbol, "days": route.days or 7, "range_key": range_key},
                    f"Calculating change for {primary_symbol}...",
                )
            if route.requires_history:
                add_tool(
                    "get_history",
                    {"symbol": primary_symbol, "days": days, "range_key": range_key},
                    f"Loading history for {primary_symbol}...",
                )
            if route.requires_info:
                add_tool(
                    "get_info",
                    {"symbol": primary_symbol},
                    f"Loading profile for {primary_symbol}...",
                )
            if route.requires_metrics:
                add_tool(
                    "get_metrics",
                    {"symbol": primary_symbol, "range_key": range_key or "1y"},
                    f"Computing risk metrics for {primary_symbol}...",
                )

        if route.requires_knowledge:
            add_tool(
                "search_knowledge",
                {"query": route.cleaned_query, "top_k": rag_top_k},
                "Searching the knowledge base...",
            )
        if route.requires_web:
            add_tool("search_web", {"query": route.cleaned_query}, "Searching recent market news...")
        if route.requires_sec:
            add_tool(
                "search_sec",
                {"query": route.cleaned_query, "symbols": route.symbols},
                "Searching SEC filings...",
            )
        return plan
