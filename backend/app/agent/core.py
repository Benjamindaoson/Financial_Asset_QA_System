"""Agent core with deterministic routing and grounded response synthesis."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.analysis.technical import TechnicalAnalyzer
from app.analysis.validator import DataValidator
from app.agent.answer_assembler import AnswerAssembler
from app.agent.route_planner import RoutePlanner
from app.agent.tool_executor import ToolExecutor
from app.config import settings
from app.core.response_generator import ResponseGenerator
from app.market import MarketDataService
from app.models import SSEEvent, Source, StructuredBlock, ToolResult
from app.models.multi_model import model_manager
from app.rag.confidence import ConfidenceScorer
from app.rag.confidence_scorer import ConfidenceScorer as AnswerConfidenceScorer
from app.rag.citation_validator import CitationValidator
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.rag.response_guard import ResponseGuard
from app.routing import QueryRoute, QueryRouter, QueryType
from app.routing.complexity_analyzer import QueryComplexityAnalyzer
from app.search import SECFilingsService, WebSearchService

try:
    from app.observability.metrics import metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("[Metrics] Prometheus metrics not available")


class AgentCore:
    """Grounded financial QA agent."""

    def __init__(self, preferred_model: Optional[str] = None):
        self.model_manager = model_manager
        self.preferred_model = preferred_model
        self.market_service = MarketDataService()

        # Initialize RAG pipeline; fall back to base RAGPipeline on failure
        self._vector_rag_available = False
        try:
            self.rag_pipeline = HybridRAGPipeline()
            _chroma_count = self.rag_pipeline.collection.count()
            if _chroma_count > 0:
                self._vector_rag_available = True
                logger.info(f"[RAG] Vector search enabled 鈥?ChromaDB has {_chroma_count} docs")
            else:
                logger.warning("[RAG] ChromaDB collection is empty, token-match fallback active")
        except Exception as _rag_init_err:
            logger.warning(
                f"[RAG] HybridRAGPipeline init failed ({_rag_init_err}), "
                "falling back to token-match retrieval"
            )
            self._vector_rag_available = False
            try:
                from app.rag.pipeline import RAGPipeline
                self.rag_pipeline = RAGPipeline()
            except Exception:
                pass  # rag_pipeline remains unset; search_knowledge will handle

        self.confidence_scorer = ConfidenceScorer()
        self.search_service = WebSearchService()
        self.sec_service = SECFilingsService()
        self.query_router = QueryRouter()
        self.complexity_analyzer = QueryComplexityAnalyzer()
        self.route_planner = RoutePlanner(self.query_router, self.complexity_analyzer)
        self.guard = ResponseGuard()
        self.technical_analyzer = TechnicalAnalyzer()
        self.data_validator = DataValidator()
        self.answer_confidence_scorer = AnswerConfidenceScorer()
        self.citation_validator = CitationValidator()
        self.answer_assembler = AnswerAssembler(
            answer_confidence_scorer=self.answer_confidence_scorer,
            citation_validator=self.citation_validator,
        )

        try:
            from app.reasoning import (
                DataIntegrator,
                DecisionEngine,
                FastAnalyzer,
                ResponseGenerator as ReasoningResponseGenerator,
            )

            self.reasoning_integrator = DataIntegrator()
            self.reasoning_analyzer = FastAnalyzer()
            self.reasoning_decision_engine = DecisionEngine()
            self.reasoning_response_builder = ReasoningResponseGenerator()
        except Exception as exc:
            logger.warning(f"[Reasoning] Structured reasoning disabled: {exc}")
            self.reasoning_integrator = None
            self.reasoning_analyzer = None
            self.reasoning_decision_engine = None
            self.reasoning_response_builder = None

        # Initialize plugin registry
        try:
            from app.plugins.base import PluginRegistry
            from app.plugins.crypto_plugin import CryptoPlugin
            self.plugin_registry = PluginRegistry()
            # Register built-in plugins
            self.plugin_registry.register(CryptoPlugin())
            logger.info(f"[Plugins] Registered {len(self.plugin_registry.plugins)} plugins")
        except Exception as e:
            logger.warning(f"[Plugins] Plugin system not available: {e}")
            self.plugin_registry = None

        self.tool_executor = ToolExecutor(
            market_service=self.market_service,
            search_service=self.search_service,
            sec_service=self.sec_service,
            rag_pipeline=getattr(self, "rag_pipeline", None),
            confidence_scorer=self.confidence_scorer,
            plugin_registry=self.plugin_registry,
            vector_rag_available=self._vector_rag_available,
            metrics_client=metrics if METRICS_AVAILABLE else None,
        )

        self.tools = self._build_tools()
        # ResponseGenerator is enabled only when a DeepSeek API key is configured
        self.response_generator: Optional[ResponseGenerator] = (
            ResponseGenerator() if settings.DEEPSEEK_API_KEY else None
        )

    def _build_tools(self) -> List[Dict[str, Any]]:
        tools = [
            {"name": "get_price", "description": "Get the latest market price.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
            {"name": "get_history", "description": "Get historical OHLCV data.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}, "days": {"type": "integer"}, "range_key": {"type": "string"}}, "required": ["symbol"]}},
            {"name": "get_change", "description": "Get price change over a time window.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}, "days": {"type": "integer"}, "range_key": {"type": "string"}}, "required": ["symbol"]}},
            {"name": "get_info", "description": "Get company or asset profile information.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
            {"name": "get_metrics", "description": "Compute volatility, return and max drawdown.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}, "range_key": {"type": "string"}}, "required": ["symbol"]}},
            {"name": "compare_assets", "description": "Compare multiple assets and prepare chart data.", "input_schema": {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}}, "range_key": {"type": "string"}}, "required": ["symbols"]}},
            {"name": "search_knowledge", "description": "Search the internal financial knowledge base.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "search_web", "description": "Search recent market news.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "search_sec", "description": "Search SEC EDGAR filings.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "symbols": {"type": "array", "items": {"type": "string"}}}, "required": ["query"]}},
        ]

        # Add plugin tools if available
        if self.plugin_registry:
            plugin_tools = self.plugin_registry.get_all_tools()
            tools.extend(plugin_tools)
            logger.info(f"[Plugins] Added {len(plugin_tools)} plugin tools to tool list")

        return tools

    async def _search_knowledge_async(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        data = await self.tool_executor.search_knowledge(query, top_k=top_k)
        self._vector_rag_available = self.tool_executor.vector_rag_available
        return data

        """Hybrid retrieval with token-match fast path for low latency.

        Flow:
          1. Try token-match first (instant, no model load) 鈥?if returns docs, use immediately
          2. If token-match empty and ChromaDB available 鈫?search_grounded() (vector+reranker)
          3. On vector error 鈫?fall back to token-match
          4. When no results + Tavily key present 鈫?trigger supplemental web search
        """
        RAG_MIN_SCORE = 0.3
        result = None
        method_used = "token_match"

        # Fast path: token-match first (synchronous, no embedding/reranker load)
        local_result = self.rag_pipeline._search_local_documents(query)
        if local_result.documents:
            result = local_result
            logger.info(
                f"[RAG] token-match fast path for {query!r}: "
                f"{len(result.documents)} docs (skipping vector+rerank)"
            )

        if result is None and self._vector_rag_available:
            try:
                result = await self.rag_pipeline.search_grounded(
                    query,
                    score_threshold=RAG_MIN_SCORE,
                    top_k=top_k,
                )
                method_used = "hybrid_vector"
                logger.info(
                    f"[RAG] vector+rerank for {query!r}: "
                    f"{len(result.documents)} docs returned (threshold={RAG_MIN_SCORE})"
                )
                if not result.documents:
                    result = local_result
                    logger.info(
                        f"[RAG] vector returned 0 docs, using token-match fallback: "
                        f"{len(local_result.documents)} docs"
                    )
            except Exception as _vec_err:
                logger.warning(
                    f"[RAG] Vector search failed ({_vec_err}), using token-match"
                )
                result = local_result
                if "chromadb" in str(_vec_err).lower() or "collection" in str(_vec_err).lower():
                    self._vector_rag_available = False
                    logger.warning("[RAG] ChromaDB failure 鈥?vector search disabled for session")

        if result is None:
            result = local_result
            logger.info(
                f"[RAG] token-match for {query!r}: {len(result.documents)} docs returned"
            )

        data = result.model_dump()
        data["method_used"] = method_used
        data["no_relevant_content"] = len(result.documents) == 0
        if hasattr(self.rag_pipeline, "multi_query_generator"):
            data["query_variants"] = self.rag_pipeline.multi_query_generator.generate_queries(query, num_queries=3)
        else:
            data["query_variants"] = [query]
        data["top_k"] = top_k

        if data["no_relevant_content"]:
            logger.info(f"[RAG] No relevant content for {query!r}, checking web supplement")
            # Trigger supplemental web search when Tavily key is available
            if settings.TAVILY_API_KEY:
                try:
                    web_supp = await self.search_service.search(query)
                    data["supplemental_web"] = web_supp.model_dump()
                    logger.info(
                        f"[RAG] Supplemental web search: "
                        f"{len(web_supp.results if hasattr(web_supp, 'results') else [])} results"
                    )
                except Exception as _w_err:
                    logger.warning(f"[RAG] Supplemental web search failed: {_w_err}")

        confidence = (
            self.confidence_scorer.calculate(query, result.documents)
            if result.documents
            else 0.0
        )
        data["confidence"] = confidence
        data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)
        return data

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.tool_executor.execute_tool(tool_name, tool_input)
        self._vector_rag_available = self.tool_executor.vector_rag_available
        return result

        start_time = time.time()
        logger.info(f"[DEBUG] Executing tool: {tool_name} with input: {tool_input}")
        try:
            data: Dict[str, Any] = {}
            if tool_name == "get_price":
                result = await self.market_service.get_price(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "get_history":
                result = await self.market_service.get_history(tool_input["symbol"], days=tool_input.get("days", 30), range_key=tool_input.get("range_key"))
                data = result.model_dump()
            elif tool_name == "get_change":
                result = await self.market_service.get_change(tool_input["symbol"], days=tool_input.get("days", 7), range_key=tool_input.get("range_key"))
                data = result.model_dump()
            elif tool_name == "get_info":
                result = await self.market_service.get_info(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "get_metrics":
                result = await self.market_service.get_metrics(tool_input["symbol"], range_key=tool_input.get("range_key", "1y"))
                data = result.model_dump()
            elif tool_name == "compare_assets":
                result = await self.market_service.compare_assets(tool_input["symbols"], range_key=tool_input.get("range_key", "1y"))
                data = result.model_dump()
            elif tool_name == "search_knowledge":
                data = await self._search_knowledge_async(tool_input["query"], top_k=tool_input.get("top_k"))
            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
                data = result.model_dump()
            elif tool_name == "search_sec":
                result = await self.sec_service.search(tool_input["query"], symbols=tool_input.get("symbols"))
                data = result.model_dump()
            else:
                # Check if it's a plugin tool
                if self.plugin_registry and self.plugin_registry.has_plugin(tool_name):
                    logger.info(f"[Plugins] Executing plugin tool: {tool_name}")
                    result = await self.plugin_registry.execute_plugin(tool_name, **tool_input)
                    data = result
                else:
                    raise ValueError(f"Unknown tool: {tool_name}")

            execution_time = time.time() - start_time

            # Record tool execution metrics
            if METRICS_AVAILABLE:
                metrics.tool_execution_duration.labels(tool=tool_name).observe(execution_time)

            return {
                "success": True,
                "tool": tool_name,
                "data": data,
                "latency_ms": int(execution_time * 1000),
                "status": "success",
                "data_source": data.get("source", tool_name),
                "cache_hit": bool(data.get("cache_hit", False)),
                "error_message": None,
            }
        except Exception as exc:
            logger.error(f"[DEBUG] Tool execution failed: tool={tool_name}, error={str(exc)}", exc_info=True)

            # Record tool error metrics
            if METRICS_AVAILABLE:
                metrics.tool_errors.labels(tool=tool_name).inc()

            return {
                "success": False,
                "tool": tool_name,
                "data": {"error": str(exc)},
                "latency_ms": int((time.time() - start_time) * 1000),
                "status": "error",
                "data_source": tool_name,
                "cache_hit": False,
                "error_message": str(exc),
            }

    async def _execute_tools_parallel(self, tool_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = await self.tool_executor.execute_tools_parallel(tool_plan)
        self._vector_rag_available = self.tool_executor.vector_rag_available
        return results

        async def execute(step: Dict[str, Any]) -> Dict[str, Any]:
            result = await self._execute_tool(step["name"], step["params"])
            result["step"] = step
            return result

        return await asyncio.gather(*[execute(step) for step in tool_plan])

    def _select_model(self, query: str) -> Optional[str]:
        if self.preferred_model:
            return self.preferred_model
        complexity = self.model_manager.classify_query(query)
        # Returns None when no models are registered (DEEPSEEK_API_KEY not set)
        return self.model_manager.select_model(complexity)

    async def _build_tool_plan(self, route: QueryRoute, rag_top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        return await self.route_planner.build_tool_plan(route, rag_top_k=rag_top_k)

        plan: List[Dict[str, Any]] = []

        def add_tool(name: str, params: Dict[str, Any], display: str) -> None:
            plan.append({"name": name, "params": params, "display": display})

        primary_symbol = route.symbols[0] if route.symbols else None
        days = route.days or 30
        range_key = route.range_key

        if route.requires_comparison and len(route.symbols) >= 2:
            add_tool("compare_assets", {"symbols": route.symbols[:4], "range_key": range_key or "1y"}, f"Comparing {', '.join(route.symbols[:4])}...")
            return plan

        if route.query_type in {QueryType.MARKET, QueryType.HYBRID} and primary_symbol:
            if route.requires_price:
                add_tool("get_price", {"symbol": primary_symbol}, f"Fetching latest price for {primary_symbol}...")
                # Auto-add 7-day change when only a price quote is requested, so the LLM
                # has trend context and can write more than a single-sentence analysis.
                if not route.requires_change:
                    add_tool("get_change", {"symbol": primary_symbol, "days": 7, "range_key": None},
                             f"Fetching 7-day change for {primary_symbol}...")
            if route.requires_change:
                add_tool("get_change", {"symbol": primary_symbol, "days": route.days or 7, "range_key": range_key}, f"Calculating change for {primary_symbol}...")
            if route.requires_history:
                add_tool("get_history", {"symbol": primary_symbol, "days": days, "range_key": range_key}, f"Loading history for {primary_symbol}...")
            if route.requires_info:
                add_tool("get_info", {"symbol": primary_symbol}, f"Loading profile for {primary_symbol}...")
            if route.requires_metrics:
                add_tool("get_metrics", {"symbol": primary_symbol, "range_key": range_key or "1y"}, f"Computing risk metrics for {primary_symbol}...")

        if route.requires_knowledge:
            add_tool(
                "search_knowledge",
                {"query": route.cleaned_query, "top_k": rag_top_k},
                "Searching the knowledge base...",
            )
        if route.requires_web:
            add_tool("search_web", {"query": route.cleaned_query}, "Searching recent market news...")
        if route.requires_sec:
            add_tool("search_sec", {"query": route.cleaned_query, "symbols": route.symbols}, "Searching SEC filings...")
        return plan

    def _normalize_tool_result(self, raw_result: Dict[str, Any]) -> ToolResult:
        return ToolResult(
            tool=raw_result["tool"],
            data=raw_result["data"],
            latency_ms=raw_result["latency_ms"],
            status=raw_result["status"],
            data_source=raw_result["data_source"],
            cache_hit=raw_result["cache_hit"],
            error_message=raw_result["error_message"],
        )

    @staticmethod
    def _strip_frontmatter(text: str) -> str:
        return AnswerAssembler.strip_frontmatter(text)

        """Remove YAML frontmatter block (---...---) from document content."""
        t = text.strip()
        if t.startswith("---"):
            end = t.find("---", 3)
            if end != -1:
                return t[end + 3:].strip()
        return t

    def _build_sources(self, tool_results: List[ToolResult]) -> List[Source]:
        return self.answer_assembler.build_sources(tool_results)

        sources: List[Source] = []
        seen: set[tuple[str, str, Optional[str]]] = set()
        for result in tool_results:
            payload = result.data
            if payload.get("source"):
                key = (payload["source"], payload.get("timestamp", datetime.utcnow().isoformat()), None)
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1]))
                    seen.add(key)
            for item in payload.get("results", []):
                key = (
                    item.get("source") or result.tool,
                    item.get("published") or payload.get("timestamp") or datetime.utcnow().isoformat(),
                    item.get("url"),
                )
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1], url=key[2]))
                    seen.add(key)
            for doc in payload.get("documents", []):
                key = (doc.get("source", result.tool), payload.get("timestamp", datetime.utcnow().isoformat()), None)
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1]))
                    seen.add(key)
        return sources

    def _map_reasoning_query_type(
        self,
        route: QueryRoute,
        technical_analysis: Optional[Dict[str, Any]],
    ) -> str:
        if technical_analysis and not technical_analysis.get("error"):
            return "technical"
        if route.requires_change:
            return "change"
        return "price"

    @staticmethod
    def _convert_technical_analysis_for_reasoning(technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
        if not technical_analysis or technical_analysis.get("error"):
            return {}

        rsi = technical_analysis.get("rsi")
        macd = technical_analysis.get("macd") or {}
        total_return = technical_analysis.get("total_return_pct") or 0.0
        trend = technical_analysis.get("trend")
        trend_map = {
            "uptrend": "涓婃定",
            "downtrend": "涓嬭穼",
            "sideways": "闇囪崱",
            "insufficient_data": "鏁版嵁涓嶈冻",
        }

        macd_signal = None
        if macd:
            macd_signal = "閲戝弶" if (macd.get("macd", 0) >= macd.get("signal", 0)) else "姝诲弶"

        if rsi is None:
            rsi_level = "neutral"
            rsi_signal = "insufficient data"
        elif rsi > 70:
            rsi_level = "overbought"
            rsi_signal = "watch for pullback risk"
        elif rsi < 30:
            rsi_level = "oversold"
            rsi_signal = "watch for rebound setup"
        else:
            rsi_level = "neutral"
            rsi_signal = "trend is balanced"

        return {
            "rsi": {
                "value": rsi,
                "level": rsi_level,
                "signal": rsi_signal,
            },
            "macd": {
                "macd": macd.get("macd"),
                "signal": macd.get("signal"),
                "histogram": macd.get("histogram"),
                "signal_type": macd_signal,
                "trend": "bullish" if macd_signal == "閲戝弶" else "bearish" if macd_signal == "姝诲弶" else "neutral",
            },
            "trend": {
                "direction": trend_map.get(trend, trend or "neutral"),
                "strength": abs(total_return),
                "change_pct": total_return,
            },
        }

    def _build_reasoning_analysis_block(
        self,
        route: QueryRoute,
        tool_results: List[ToolResult],
        technical_analysis: Optional[Dict[str, Any]],
    ) -> Optional[StructuredBlock]:
        if not all(
            [
                self.reasoning_integrator,
                self.reasoning_analyzer,
                self.reasoning_decision_engine,
                self.reasoning_response_builder,
            ]
        ):
            return None
        if route.query_type not in {QueryType.MARKET, QueryType.HYBRID}:
            return None

        payloads = [
            {"success": result.status == "success", "tool": result.tool, "data": result.data}
            for result in tool_results
            if result.status == "success"
        ]
        if not payloads:
            return None

        query_context = {"query_type": self._map_reasoning_query_type(route, technical_analysis)}
        integrated = self.reasoning_integrator.integrate(payloads, query_context)
        primary_symbol = route.symbols[0] if route.symbols else next(iter(integrated.get("symbols", {})), None)
        if primary_symbol and primary_symbol in integrated.get("symbols", {}):
            technical_payload = self._convert_technical_analysis_for_reasoning(technical_analysis or {})
            if technical_payload:
                integrated["symbols"][primary_symbol]["technical"] = technical_payload

        analysis = self.reasoning_analyzer.analyze(integrated, query_context)
        if not analysis.get("success"):
            return None
        decision = self.reasoning_decision_engine.generate_decision(analysis, integrated)
        if not decision.get("success"):
            return None
        response = self.reasoning_response_builder.generate(analysis, decision, integrated)
        if not response.get("success"):
            return None

        reference_section = response.get("sections", {}).get("reference_view", {})
        reference_items = reference_section.get("items", [])
        overall = next((item for item in reference_items if item.get("type") == "overall"), {})
        opportunities = next((item for item in reference_items if item.get("type") == "opportunities"), {})
        risks = next((item for item in reference_items if item.get("type") == "risks"), {})
        watch_points: List[str] = []
        for category in response.get("sections", {}).get("risk_warnings", {}).get("categories", []):
            watch_points.extend(category.get("risks", []))

        trend_summary = overall.get("description") or analysis.get("summary")
        block_data = {
            "trend_summary": trend_summary,
            "drivers": opportunities.get("points", [])[:4],
            "risks": risks.get("points", [])[:4],
            "watch_points": watch_points[:4],
            "confidence": (
                f"{overall.get('score', 0):.0%}"
                if isinstance(overall.get("score"), (float, int))
                else None
            ),
        }
        if not any(block_data.get(key) for key in ("trend_summary", "drivers", "risks", "watch_points")):
            return None

        return StructuredBlock(type="analysis", title="Structured Analysis", data=block_data)

    def _build_llm_context(
        self, tool_results: List[ToolResult]
    ) -> tuple[str, str, str, float, float]:
        """Extract structured context from tool results for LLM consumption.

        Returns:
            (api_data_text, rag_context, news_context, api_completeness, rag_relevance)
        """
        api_data_lines: List[str] = []
        rag_context = ""
        news_context = ""
        rag_relevance = 0.0

        successful = [r for r in tool_results if r.status == "success"]
        market_tools = {"get_price", "get_change", "get_history", "get_info", "get_metrics", "compare_assets"}

        for result in successful:
            if result.tool == "search_knowledge":
                docs = result.data.get("documents", [])
                no_match = result.data.get("no_relevant_content", False)
                method_used = result.data.get("method_used", "unknown")
                logger.info(
                    f"[RAG] _build_llm_context: method={method_used}, "
                    f"docs={len(docs)}, no_match={no_match}"
                )
                if no_match or not docs:
                    rag_context = "鐭ヨ瘑搴撲腑鏈壘鍒颁笌璇ラ棶棰樼洿鎺ョ浉鍏崇殑鍐呭"
                    supp_web = result.data.get("supplemental_web")
                    if supp_web:
                        supp_items = supp_web.get("results", [])[:2]
                        if supp_items:
                            supp_lines = "\n".join(
                                f"- {item.get('title', '')}: {item.get('snippet', '')[:150]}"
                                for item in supp_items
                            )
                            rag_context += f"\n\n銆愯ˉ鍏呯綉缁滄悳绱㈢粨鏋溿€慭n{supp_lines}"
                else:
                    rag_context = "\n\n".join(
                        f"[Source: {doc.get('source', 'knowledge_base')}]\n"
                        f"{self._strip_frontmatter(doc.get('content', ''))[:500]}"
                        for doc in docs[:3]
                    )
                    rag_relevance = float(result.data.get("confidence", 0.5))
            elif result.tool == "get_price":
                data = result.data
                if data.get("price") is not None:
                    api_data_lines.append(f"Current price: {data['price']:.2f} {data.get('currency', 'USD')}")
                if data.get("change") is not None and data.get("change_pct") is not None:
                    api_data_lines.append(f"Daily move: {data['change']:+.2f} ({data['change_pct']:+.2f}%)")
            elif result.tool == "get_change":
                data = result.data
                if data.get("change_pct") is not None:
                    days_n = data.get("days", "N")
                    start = data.get("start_price")
                    end = data.get("end_price")
                    pct = data["change_pct"]
                    trend = data.get("trend", "鏈煡")
                    if start is not None and end is not None:
                        api_data_lines.append(
                            f"{days_n}-day performance: {start:.2f} -> {end:.2f} ({pct:+.2f}%)"
                        )
                    else:
                        api_data_lines.append(f"{days_n}-day change: {pct:+.2f}%")
                    api_data_lines.append(f"Trend assessment: {trend}")
            elif result.tool == "get_history":
                data = result.data
                hist_points = data.get("data", [])
                if hist_points:
                    highs = [p.get("high") for p in hist_points if p.get("high") is not None]
                    lows = [p.get("low") for p in hist_points if p.get("low") is not None]
                    dates = [p.get("date") for p in hist_points if p.get("date")]

                    # Today's OHLCV (last data point)
                    last = hist_points[-1]
                    if last.get("open") is not None:
                        vol = last.get("volume", 0)
                        vol_str = f"{vol:,.0f}"
                        api_data_lines.append(
                            f"寮€鐩橈細{last['open']:.2f} / 鏈€楂橈細{last.get('high', last['open']):.2f}"
                            f" / 鏈€浣庯細{last.get('low', last['open']):.2f} / 鎴愪氦閲忥細{vol_str}"
                        )

                    if highs and lows:
                        max_high = max(highs)
                        min_low = min(lows)
                        max_high_idx = highs.index(max_high)
                        min_low_idx = lows.index(min_low)
                        max_high_date = dates[max_high_idx] if max_high_idx < len(dates) else "鏈煡"
                        min_low_date = dates[min_low_idx] if min_low_idx < len(dates) else "鏈煡"
                        days_n = data.get("days", len(hist_points))
                        api_data_lines.append(f"{days_n}-day high: {max_high:.2f} ({max_high_date})")
                        api_data_lines.append(f"{days_n}-day low: {min_low:.2f} ({min_low_date})")
            elif result.tool == "get_metrics":
                data = result.data
                if data.get("rsi") is not None:
                    rsi = data["rsi"]
                    if rsi < 30:
                        rsi_zone = "瓒呭崠鍖哄煙锛堜綆浜?0涓鸿秴鍗栧尯鍩燂紝鎰忓懗鐫€杩戞湡璺屽箙杈冨ぇ锛屽彲鑳藉瓨鍦ㄨ秴璺屽弽寮规満浼氾級"
                    elif rsi > 70:
                        rsi_zone = "瓒呬拱鍖哄煙锛堥珮浜?0涓鸿秴涔板尯鍩燂紝鎰忓懗鐫€杩戞湡娑ㄥ箙杈冨ぇ锛屽彲鑳介潰涓村洖璋冨帇鍔涳級"
                    else:
                        rsi_zone = "涓€у尯鍩燂紙30-70涔嬮棿锛屽绌哄姏閲忕浉瀵瑰潎琛★級"
                    api_data_lines.append(f"RSI(14): {rsi:.1f} ({rsi_zone})")
                if data.get("max_drawdown_pct") is not None:
                    api_data_lines.append(f"鏈€澶у洖鎾わ細{data['max_drawdown_pct']:+.2f}%")
                if data.get("annualized_volatility") is not None:
                    api_data_lines.append(f"娉㈠姩鐜囷細{data['annualized_volatility']:.2f}%")
                if data.get("total_return_pct") is not None:
                    api_data_lines.append(f"鍖洪棿鎬绘敹鐩婏細{data['total_return_pct']:+.2f}%")
            elif result.tool in ("search_web", "search_sec"):
                items = result.data.get("results", [])[:5]
                if result.tool == "search_web":
                    news_items = []
                    for i, item in enumerate(items):
                        title = item.get('title', '鏈煡鏍囬')
                        source = item.get('source', '鏈煡鏉ユ簮')
                        # Prefer full content over snippet; show up to 300 chars
                        content = (item.get('content') or item.get('snippet') or '').strip()
                        snippet = content[:300] if content else "(no detailed summary)"
                        news_items.append(
                            f"News {i + 1}: {title}\n"
                            f"Source: {source}\n"
                            f"Summary: {snippet}"
                        )
                    news_context = "\n\n".join(news_items) if news_items else ""

        api_completeness = (
            len([r for r in successful if r.tool in market_tools]) / max(len(tool_results), 1)
        )

        api_data_text = "\n".join(api_data_lines) if api_data_lines else "No market data available"
        return (
            api_data_text,
            rag_context or "No knowledge base results available",
            news_context or "No news data available",
            api_completeness,
            rag_relevance,
        )

    def _compose_answer(
        self,
        query: str,
        route: QueryRoute,
        tool_results: List[ToolResult],
        technical_analysis: Optional[Dict[str, Any]],
        validation: Dict[str, Any],
    ) -> tuple[str, List[StructuredBlock]]:
        by_tool = {result.tool: result.data for result in tool_results if result.status == "success"}
        blocks: List[StructuredBlock] = []
        warnings: List[str] = []

        if route.refuses_advice:
            warnings.append("The system does not provide buy/sell recommendations or target prices.")
        if validation["level"] == "low":
            warnings.append("This analysis is based on public market data and is for reference only.")

        comparison = by_tool.get("compare_assets")
        if comparison:
            rows = comparison.get("rows", [])
            best_return = max(rows, key=lambda item: item.get("total_return_pct") or float("-inf"), default=None)
            lowest_drawdown = min(rows, key=lambda item: item.get("max_drawdown_pct") or float("inf"), default=None)
            text = "Asset comparison completed."
            if best_return:
                text += f" {best_return['symbol']} has the strongest period return at {best_return.get('total_return_pct', 0):+.2f}%."
            if lowest_drawdown and lowest_drawdown.get("max_drawdown_pct") is not None:
                text += f" {lowest_drawdown['symbol']} has the shallowest drawdown at {lowest_drawdown['max_drawdown_pct']:+.2f}%."
            blocks.append(StructuredBlock(type="table", title="Asset Comparison", data={"columns": ["symbol", "price", "total_return_pct", "annualized_volatility", "max_drawdown_pct"], "rows": rows}))
            blocks.append(StructuredBlock(type="chart", title="Comparison Trend", data={"chart_type": "comparison", "range_key": comparison.get("range_key"), "series": comparison.get("chart", [])}))
            if warnings:
                blocks.append(StructuredBlock(type="warning", title="Risk Notice", data={"items": warnings}))
            return text, blocks

        price = by_tool.get("get_price")
        change = by_tool.get("get_change")
        metrics = by_tool.get("get_metrics")
        history = by_tool.get("get_history")
        info = by_tool.get("get_info")
        knowledge = by_tool.get("search_knowledge")
        sec_results = by_tool.get("search_sec")
        web_results = by_tool.get("search_web")

        # Block 1: Chart (always first if we have history data)
        if history and history.get("data"):
            days = route.days
            if days and days <= 7:
                default_range = "7D"
            elif days and days <= 30:
                default_range = "1M"
            elif "褰撳墠" in query or "鑲′环" in query:
                default_range = "YTD"
            elif "杩戞湡" in query or "璧板娍" in query:
                default_range = "3M"
            else:
                default_range = "YTD"
            blocks.append(StructuredBlock(
                type="chart", title="Price Trend",
                data={
                    "chart_type": "history",
                    "symbol": history["symbol"],
                    "range_key": history.get("range_key"),
                    "series": history.get("data", []),
                    "default_range": default_range,
                }
            ))

        # Block 2: Key Metrics (price + change summary)
        if price and price.get("price") is not None:
            km_data: Dict[str, Any] = {
                "price": price.get("price"),
                "currency": price.get("currency", "USD"),
                "symbol": price.get("symbol"),
                "name": price.get("name") or (info or {}).get("name"),
            }
            if history and history.get("data"):
                hist_data = history["data"]
                last = hist_data[-1]
                km_data.update({
                    "open": last.get("open"),
                    "high": last.get("high"),
                    "low": last.get("low"),
                    "volume": last.get("volume"),
                })
                # 鍖洪棿鏈€楂?鏈€浣?鎸箙锛堢敤浜庤蛋鍔挎杩版寚鏍囧崱鐗囷級
                highs = [p.get("high") for p in hist_data if p.get("high") is not None]
                lows = [p.get("low") for p in hist_data if p.get("low") is not None]
                if highs and lows:
                    period_high = max(highs)
                    period_low = min(lows)
                    km_data["period_high"] = period_high
                    km_data["period_low"] = period_low
                    if period_low and period_low > 0:
                        km_data["period_amplitude_pct"] = round((period_high - period_low) / period_low * 100, 2)
            # 鍏滃簳锛氭棤 history 鏃剁敤 change 鐨?start/end 杩戜技
            if change and km_data.get("period_high") is None and change.get("start_price") is not None and change.get("end_price") is not None:
                s, e = float(change["start_price"]), float(change["end_price"])
                km_data["period_high"] = max(s, e)
                km_data["period_low"] = min(s, e)
                if min(s, e) > 0:
                    km_data["period_amplitude_pct"] = round((max(s, e) - min(s, e)) / min(s, e) * 100, 2)
            if change and change.get("change_pct") is not None:
                km_data.update({
                    "change_pct": change.get("change_pct"),
                    "start_price": change.get("start_price"),
                    "end_price": change.get("end_price"),
                    "period_days": change.get("days", 7),
                    "trend": change.get("trend"),
                })
                if change.get("end_price") is not None and change.get("start_price") is not None:
                    km_data["change"] = round(float(change["end_price"]) - float(change["start_price"]), 2)
            blocks.append(StructuredBlock(type="key_metrics", title="鍏抽敭鏁版嵁", data=km_data))
        elif change and change.get("change_pct") is not None:
            km_data = {
                "change_pct": change.get("change_pct"),
                "start_price": change.get("start_price"),
                "end_price": change.get("end_price"),
                "period_days": change.get("days"),
                "trend": change.get("trend"),
                "symbol": change.get("symbol"),
                "name": (price or {}).get("name") or (info or {}).get("name"),
                "currency": "USD",
            }
            if change.get("end_price") is not None and change.get("start_price") is not None:
                km_data["change"] = round(float(change["end_price"]) - float(change["start_price"]), 2)
            if history and history.get("data"):
                hist_data = history["data"]
                highs = [p.get("high") for p in hist_data if p.get("high") is not None]
                lows = [p.get("low") for p in hist_data if p.get("low") is not None]
                if highs and lows:
                    km_data["period_high"] = max(highs)
                    km_data["period_low"] = min(lows)
                    pl = min(lows)
                    if pl and pl > 0:
                        km_data["period_amplitude_pct"] = round((max(highs) - pl) / pl * 100, 2)
            # 鍏滃簳锛氭棤 history 鏃剁敤 start/end 杩戜技
            if km_data.get("period_high") is None and km_data.get("start_price") is not None and km_data.get("end_price") is not None:
                s, e = float(km_data["start_price"]), float(km_data["end_price"])
                km_data["period_high"] = max(s, e)
                km_data["period_low"] = min(s, e)
                pl = min(s, e)
                if pl > 0:
                    km_data["period_amplitude_pct"] = round((max(s, e) - pl) / pl * 100, 2)
            blocks.append(StructuredBlock(type="key_metrics", title="鍏抽敭鏁版嵁", data=km_data))

        # Block 3: Risk/Return Table
        if metrics and metrics.get("total_return_pct") is not None:
            blocks.append(StructuredBlock(
                type="table", title="Risk and Return Metrics",
                data={
                    "columns": ["metric", "value"],
                    "rows": [
                        {"metric": "Range", "value": metrics.get("range_key")},
                        {"metric": "Total Return", "value": f"{metrics['total_return_pct']:+.2f}%"},
                        {"metric": "Annualized Volatility", "value": f"{metrics['annualized_volatility']:.2f}%"},
                        {"metric": "Max Drawdown", "value": f"{metrics['max_drawdown_pct']:+.2f}%"},
                        {"metric": "Annualized Return", "value": f"{metrics.get('annualized_return_pct', 0):+.2f}%"},
                        {"metric": "Sharpe", "value": f"{metrics.get('sharpe_ratio', 0):.2f}" if metrics.get("sharpe_ratio") is not None else "N/A"},
                    ],
                },
            ))

        reasoning_block = self._build_reasoning_analysis_block(route, tool_results, technical_analysis)
        if reasoning_block:
            blocks.append(reasoning_block)

        # Block 4: Knowledge Quote (KNOWLEDGE / HYBRID routes only) 鈥?鎵╁睍涓?items + text 鍏煎
        if knowledge and knowledge.get("documents"):
            if route.query_type in (QueryType.KNOWLEDGE, QueryType.HYBRID):
                docs = knowledge["documents"][:5]
                method_used = knowledge.get("method_used", "unknown")
                items = []
                preview_lines = []
                for i, doc in enumerate(docs):
                    content = doc.get("content", "")
                    source = doc.get("source", "鏈煡")
                    score = doc.get("score", 0.0)
                    preview = self._strip_frontmatter(content)[:200].strip()
                    items.append({
                        "id": i + 1,
                        "source": source,
                        "score": round(float(score), 2),
                        "preview": preview,
                        "method": method_used,
                    })
                    preview_lines.append(f"- {preview[:120]}")
                blocks.append(StructuredBlock(
                    type="quote", title="Knowledge Base Excerpts",
                    data={
                        "text": "\n".join(preview_lines),
                        "items": items,
                        "method_used": method_used,
                    }
                ))

        # Block 5: SEC fallback bullets (removed when LLM succeeds)
        if sec_results and sec_results.get("results"):
            blocks.append(StructuredBlock(
                type="bullets", title="SEC/璐㈡姤鏉ユ簮",
                data={"items": [
                    f"{item.get('title')} ({item.get('published') or 'unknown'})"
                    for item in sec_results["results"][:3]
                ]}
            ))
        # Block 5b: News cards (type="news" 鈥?NOT removed when LLM succeeds)
        def _news_items_from_results(results: list) -> list:
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", "鏈煡"),
                    "published": item.get("published") or "",
                    "snippet": (item.get("content") or item.get("snippet") or "")[:200],
                }
                for item in results[:5]
                if item.get("title")
            ]
        news_items: List[Dict[str, Any]] = []
        if web_results and web_results.get("results"):
            news_items = _news_items_from_results(web_results["results"])
        elif knowledge and knowledge.get("no_relevant_content"):
            supp_web = knowledge.get("supplemental_web")
            if supp_web and supp_web.get("results"):
                news_items = _news_items_from_results(supp_web["results"])
        if news_items:
            blocks.append(StructuredBlock(
                type="news", title="鐩稿叧鏂伴椈",
                data={"items": news_items}
            ))

        if warnings:
            blocks.append(StructuredBlock(type="warning", title="椋庨櫓鎻愮ず", data={"items": warnings}))

        # Template fallback text (replaced by LLM analysis when available)
        fragments: List[str] = []
        if price and price.get("price") is not None:
            fragments.append(
                f"{price['symbol']} 鏈€鏂颁环鏍?{price['price']:.2f} {price.get('currency') or ''}".strip()
            )
        if change and change.get("change_pct") is not None:
            fragments.append(f"{change.get('days', 7)}鏃ユ定璺?{change['change_pct']:+.2f}%")
        if knowledge and not price and not change and not metrics:
            docs = knowledge.get("documents", [])
            if docs:
                first_doc = self._strip_frontmatter(docs[0]["content"]).replace("\n", " ")
                fragments = [first_doc[:140].strip()]
        if fragments:
            return ". ".join(fragments) + ".", blocks
        return "", blocks

    def _load_demo_cache(self) -> Optional[Dict[str, Any]]:
        """Load demo cache if enabled."""
        if not settings.DEMO_CACHE_ENABLED:
            return None
        try:
            from pathlib import Path
            path = Path(__file__).resolve().parents[2] / settings.DEMO_CACHE_PATH
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    async def run(self, query: str, model_name: Optional[str] = None) -> AsyncGenerator[SSEEvent, None]:
        request_id = str(uuid.uuid4())
        tool_results: List[ToolResult] = []
        model_name = model_name or self._select_model(query)
        model_config = self.model_manager.models.get(model_name)
        if model_name and model_name not in self.model_manager.models:
            yield SSEEvent(type="error", message=f"Model {model_name} not found", code="MODEL_NOT_FOUND")
            return

        logger.info(f"[DEBUG] AgentCore.run() called with query: {query}")

        # Record query metrics
        if METRICS_AVAILABLE:
            metrics.query_total.inc()

        start_time = time.time()

        # Demo cache: 鑻ュ惎鐢ㄤ笖闂鍖归厤锛岀洿鎺ヨ繑鍥炵紦瀛樼瓟妗堬紙婕旂ず鐢級
        cache = self._load_demo_cache()
        if cache:
            normalized = query.strip()
            if normalized in cache:
                cached = cache[normalized]
                logger.info(f"[DEMO] Cache hit for {normalized[:40]}...")
                yield SSEEvent(type="model_selected", model=model_name, provider=getattr(model_config, "provider", "deepseek"), complexity="medium")
                yield SSEEvent(type="blocks", data={"blocks": cached.get("blocks", []), "route": cached.get("route")})
                if cached.get("text"):
                    yield SSEEvent(type="chunk", text=cached["text"])
                yield SSEEvent(
                    type="done",
                    verified=True,
                    sources=[Source(name=s.get("name", ""), timestamp=s.get("timestamp", "")) for s in cached.get("sources", [])],
                    request_id=request_id,
                    model=model_name,
                    tokens_input=len(query) // 4,
                    tokens_output=len(cached.get("text", "")) // 4,
                    data={
                        "confidence": {"level": "high", "score": 90},
                        "blocks": cached.get("blocks", []),
                        "route": cached.get("route"),
                        "llm_used": cached.get("llm_used", False),
                        "disclaimer": "以上内容仅供参考，不构成投资建议。",
                        "rag_citations": cached.get("rag_citations", []),
                        "tool_latencies": cached.get("tool_latencies", []),
                    },
                )
                return

        yield SSEEvent(type="model_selected", model=model_name, provider=getattr(model_config, "provider", "deepseek"), complexity=self.model_manager.classify_query(query))
        route, complexity_score = await self.route_planner.analyze(query)
        logger.info(f"[DEBUG] Route: type={route.query_type}, requires_knowledge={route.requires_knowledge}")

        logger.info(
            f"[Complexity] Query complexity: {complexity_score.level}, "
            f"score={complexity_score.score:.2f}, "
            f"recommended_top_k={complexity_score.rag_top_k}, "
            f"timeout_multiplier={complexity_score.timeout_multiplier:.1f}"
        )

        if route.refuses_advice:
            refusal = (
                "I cannot provide buy, sell, or target-price advice. "
                "You can continue asking for prices, historical trends, volatility, drawdowns, or public filings."
            )
            yield SSEEvent(type="chunk", text=refusal)
            yield SSEEvent(
                type="done",
                verified=True,
                sources=[],
                request_id=request_id,
                model=model_name,
                tokens_input=len(query) // 4,
                tokens_output=len(refusal) // 4,
                data={
                    "confidence": {"level": "high", "score": 100},
                    "blocks": [
                        StructuredBlock(
                            type="warning",
                            title="Compliance Notice",
                            data={"items": ["This system provides factual data and risk indicators, not investment advice."]},
                        ).model_dump()
                    ],
                    "route": {"type": route.query_type.value, "symbols": route.symbols},
                    "disclaimer": "以上内容仅供参考，不构成投资建议。",
                },
            )
            return

        try:
            tool_plan = await self._build_tool_plan(route, rag_top_k=complexity_score.rag_top_k)
            logger.info(f"[DEBUG] Tool plan: {[step['name'] for step in tool_plan]}")
            for step in tool_plan:
                yield SSEEvent(type="tool_start", name=step["name"], display=step["display"])

            raw_results = await self._execute_tools_parallel(tool_plan) if tool_plan else []
            for raw_result in raw_results:
                if not raw_result["success"]:
                    continue
                logger.info(f"[DEBUG] Raw result before normalization: tool={raw_result['tool']}")
                logger.info(f"[DEBUG] Raw result data keys: {list(raw_result['data'].keys())}")
                if raw_result['tool'] == 'search_knowledge':
                    logger.info(f"[DEBUG] search_knowledge raw data.documents: {raw_result['data'].get('documents')}")
                tool_result = self._normalize_tool_result(raw_result)
                logger.info(f"[DEBUG] After normalization: tool={tool_result.tool}, data type={type(tool_result.data)}")
                if tool_result.tool == 'search_knowledge':
                    logger.info(f"[DEBUG] search_knowledge normalized data.documents: {tool_result.data.get('documents')}")
                tool_results.append(tool_result)
                yield SSEEvent(type="tool_data", tool=raw_result["tool"], data=raw_result["data"])

            validation = self.data_validator.validate_tool_results(tool_results)
            sources = self._build_sources(tool_results)
            if self.data_validator.should_block_response(validation):
                fallback = self.data_validator.get_fallback_message(validation, route.symbols[0] if route.symbols else "褰撳墠闂")
                yield SSEEvent(type="chunk", text=fallback)
                yield SSEEvent(
                    type="done",
                    verified=False,
                    sources=sources,
                    request_id=request_id,
                    model=model_name,
                    tokens_input=len(query) // 4,
                    tokens_output=len(fallback) // 4,
                    data={
                        "confidence": {"level": validation["level"], "score": validation["confidence"]},
                        "blocks": [StructuredBlock(type="warning", title="Data Unavailable", data={"items": validation["missing"]}).model_dump()],
                        "route": {"type": route.query_type.value, "symbols": route.symbols, "range_key": route.range_key},
                        "disclaimer": "以上内容仅供参考，不构成投资建议。",
                    },
                )
                return

            technical_analysis = None
            for result in tool_results:
                if result.tool == "get_history" and len(result.data.get("data", [])) >= 20:
                    from app.models import PricePoint

                    technical_analysis = self.technical_analyzer.analyze([PricePoint(**item) for item in result.data["data"]])
                    break

            # _compose_answer generates structured blocks (charts/tables) + a template fallback text
            template_text, blocks = self._compose_answer(query, route, tool_results, technical_analysis, validation)

            # 鎻愬墠鎺ㄩ€?blocks锛堝浘琛?浠锋牸/鏂伴椈绛夛級锛岀敤鎴锋棤闇€绛夊緟 LLM 鍗冲彲鐪嬪埌鏁版嵁
            if blocks:
                yield SSEEvent(type="blocks", data={"blocks": [b.model_dump() for b in blocks], "route": {"type": route.query_type.value, "symbols": route.symbols, "range_key": route.range_key}})

            # Push the template summary text first (hidden by frontend when analysis block exists)
            # as per prompt, if we are to use LLM, we shouldn't push template_text
            if not (self.response_generator and settings.DEEPSEEK_API_KEY):
                if template_text:
                    yield SSEEvent(type="chunk", text=template_text)

            # Attempt LLM-based analysis generation as a separate structured block
            llm_used = False
            final_answer_text = template_text
            if self.response_generator and settings.DEEPSEEK_API_KEY:
                try:
                    yield SSEEvent(type="tool_start", name="llm_generate", display="姝ｅ湪鐢熸垚 AI 鍒嗘瀽...")
                    api_data, rag_context, news_context, api_completeness, rag_relevance = self._build_llm_context(tool_results)
                    # Enrich api_data with locally-computed technical indicators
                    if technical_analysis and not technical_analysis.get("error"):
                        tech_lines = []
                        ma5 = technical_analysis.get("ma5")
                        ma20 = technical_analysis.get("ma20")
                        if ma5 is not None:
                            tech_lines.append(f"MA5: {ma5:.2f}")
                        if ma20 is not None:
                            tech_lines.append(f"MA20: {ma20:.2f}")
                        vol = technical_analysis.get("volume")
                        if vol and isinstance(vol, dict) and vol.get("ratio") is not None:
                            r = vol["ratio"]
                            if r > 1:
                                tech_lines.append(f"Volume: {r:.1f}x above the 20-day average")
                            elif r < 1 and r > 0:
                                tech_lines.append(f"Volume: {r:.1f}x of the 20-day average")
                            else:
                                tech_lines.append("Volume: in line with the 20-day average")
                        sup = technical_analysis.get("support")
                        res = technical_analysis.get("resistance")
                        if sup is not None:
                            tech_lines.append(f"鏀拺浣嶏細{sup:.2f}")
                        if res is not None:
                            tech_lines.append(f"闃诲姏浣嶏細{res:.2f}")
                        rsi = technical_analysis.get("rsi")
                        if rsi is not None:
                            if rsi < 30:
                                rsi_zone = "瓒呭崠鍖哄煙锛堜綆浜?0锛岃繎鏈熻穼骞呰緝澶э紝瀛樺湪瓒呰穼鍙嶅脊闇€姹傦級"
                            elif rsi > 70:
                                rsi_zone = "overbought zone"
                            else:
                                rsi_zone = "涓€у尯鍩燂紙30-70涔嬮棿锛屽绌哄姏閲忕浉瀵瑰潎琛★級"
                            tech_lines.append(f"RSI(14): {rsi:.1f} ({rsi_zone})")
                        if technical_analysis.get("max_drawdown_pct") is not None:
                            tech_lines.append(f"Max drawdown: {technical_analysis['max_drawdown_pct']:+.2f}%")
                        trend = technical_analysis.get("trend")
                        if trend and trend != "insufficient_data":
                            trend_cn = {"uptrend": "涓婃定", "downtrend": "涓嬭穼", "sideways": "妯洏"}.get(trend, trend)
                            tech_lines.append(f"Trend: {trend_cn}")
                        if tech_lines:
                            api_data = api_data + "\n\n鎶€鏈寚鏍囷細\n" + "\n".join(tech_lines)

                    # Stream LLM response character by character
                    llm_text_buffer = []
                    async for chunk in self.response_generator.generate_stream(
                        user_question=route.cleaned_query,
                        api_data=api_data,
                        rag_context=rag_context,
                        news_context=news_context,
                        api_completeness=api_completeness,
                        rag_relevance=rag_relevance,
                        route_type=route.query_type.value,
                    ):
                        llm_text_buffer.append(chunk)
                        # Yield streaming chunk to frontend
                        yield SSEEvent(type="analysis_chunk", text=chunk)

                    llm_text = "".join(llm_text_buffer)
                    if llm_text and len(llm_text.strip()) > 10:
                        final_answer_text = llm_text.strip()
                        # Add LLM analysis as a structured block
                        blocks.append(StructuredBlock(
                            type="analysis",
                            title="AI 鍒嗘瀽",
                            data={"text": llm_text.strip()}
                        ))
                        llm_used = True
                        # When LLM analysis succeeded, remove redundant fallback blocks
                        blocks = [b for b in blocks if b.type not in ("bullets", "warning", "analysis")] + [blocks[-1]]
                        logger.info(f"[LLM] Analysis generated successfully ({len(llm_text)} chars)")
                except asyncio.TimeoutError:
                    logger.warning("[LLM] Generator timed out, skipping AI analysis")
                    if template_text:
                        yield SSEEvent(type="chunk", text=template_text)
                except Exception as llm_exc:
                    logger.warning(f"[LLM] Generator failed ({llm_exc}), skipping AI analysis")
                    if template_text:
                        yield SSEEvent(type="chunk", text=template_text)

            self.model_manager.record_usage(model_name=model_name, tokens_input=len(query) // 4, tokens_output=len(final_answer_text) // 4, success=True)
            ordered_blocks = self.answer_assembler.order_blocks(blocks, route)
            done_data = self.answer_assembler.build_done_data(
                query=query,
                route=route,
                tool_results=tool_results,
                blocks=ordered_blocks,
                validation=validation,
                llm_used=llm_used,
                final_answer_text=final_answer_text,
                complexity_score=complexity_score,
                disclaimer="以上内容仅供参考，不构成投资建议。",
            )

            # Record metrics at completion
            if METRICS_AVAILABLE:
                duration = time.time() - start_time
                metrics.query_duration.observe(duration)
                metrics.confidence_score.set(validation["confidence"])
                if llm_used:
                    # Estimate token usage (rough approximation)
                    estimated_tokens = len(query) // 4 + len(final_answer_text) // 4
                    metrics.llm_token_usage.inc(estimated_tokens)

            yield SSEEvent(type="done", verified=self.guard.validate(final_answer_text, tool_results), sources=sources, request_id=request_id, model=model_name, tokens_input=len(query) // 4, tokens_output=len(final_answer_text) // 4, data=done_data)
        except Exception as exc:
            self.model_manager.record_usage(model_name=model_name, tokens_input=len(query) // 4, tokens_output=0, success=False)

            # Record error metrics
            if METRICS_AVAILABLE:
                metrics.query_errors.inc()

            yield SSEEvent(type="error", message=str(exc), code="LLM_ERROR", model=model_name)

    def get_available_models(self) -> List[Dict[str, Any]]:
        return self.model_manager.list_models()

    def get_usage_report(self) -> Dict[str, Any]:
        return self.model_manager.get_usage_report()

