"""Tool execution helpers for the agent runtime."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module load time
_multi_domain_pipeline = None


def _get_multi_domain_pipeline():
    global _multi_domain_pipeline
    if _multi_domain_pipeline is None:
        from app.rag.multi_domain_pipeline import MultiDomainRAGPipeline
        _multi_domain_pipeline = MultiDomainRAGPipeline()
    return _multi_domain_pipeline


class ToolExecutor:
    """Execute tool calls and keep retrieval fallbacks contained."""

    def __init__(
        self,
        market_service: Any,
        search_service: Any,
        sec_service: Any,
        rag_pipeline: Any,
        confidence_scorer: Any,
        plugin_registry: Any = None,
        vector_rag_available: bool = False,
        metrics_client: Any = None,
    ) -> None:
        self.market_service = market_service
        self.search_service = search_service
        self.sec_service = sec_service
        self.rag_pipeline = rag_pipeline
        self.confidence_scorer = confidence_scorer
        self.plugin_registry = plugin_registry
        self.vector_rag_available = vector_rag_available
        self.metrics = metrics_client

    async def search_knowledge(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        # Use multi-domain pipeline when enabled and single pipeline has no local docs
        _single_has_local = (
            self.rag_pipeline
            and hasattr(self.rag_pipeline, "_local_documents")
            and bool(getattr(self.rag_pipeline, "_local_documents", None))
        )
        if settings.MULTI_DOMAIN_ENABLED and not _single_has_local:
            try:
                md_pipeline = _get_multi_domain_pipeline()
                md_result, md_domain = await md_pipeline.search(query, top_k=top_k or settings.RAG_TOP_K)
                if md_result.documents:
                    data = md_result.model_dump()
                    data["method_used"] = "multi_domain"
                    data["domain"] = md_domain
                    data["no_relevant_content"] = False
                    data["query_variants"] = [query]
                    data["top_k"] = top_k
                    confidence = self.confidence_scorer.calculate(query, md_result.documents)
                    data["confidence"] = confidence
                    data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)
                    return data
                logger.info("[MultiDomain] No docs returned, falling back to single pipeline")
            except Exception as exc:
                logger.warning("[MultiDomain] Pipeline failed, falling back to single pipeline: %s", exc)

        if not self.rag_pipeline or not hasattr(self.rag_pipeline, "_search_local_documents"):
            logger.warning("[RAG] Retrieval pipeline unavailable, returning empty knowledge result")
            return {
                "documents": [],
                "total_found": 0,
                "method_used": "unavailable",
                "no_relevant_content": True,
                "query_variants": [query],
                "top_k": top_k,
                "confidence": 0.0,
                "confidence_level": "low",
            }

        rag_min_score = 0.3
        result = None
        method_used = "token_match"

        local_result = self.rag_pipeline._search_local_documents(query)
        if local_result.documents:
            result = local_result
            logger.info(
                "[RAG] token-match fast path for %r: %s docs (skipping vector+rerank)",
                query,
                len(result.documents),
            )

        if result is None and self.vector_rag_available:
            try:
                result = await self.rag_pipeline.search_grounded(
                    query,
                    score_threshold=rag_min_score,
                    top_k=top_k,
                )
                method_used = "hybrid_vector"
                logger.info(
                    "[RAG] vector+rerank for %r: %s docs returned (threshold=%.1f)",
                    query,
                    len(result.documents),
                    rag_min_score,
                )
                if not result.documents:
                    result = local_result
                    logger.info(
                        "[RAG] vector returned 0 docs, using token-match fallback: %s docs",
                        len(local_result.documents),
                    )
            except Exception as exc:
                logger.warning("[RAG] Vector search failed (%s), using token-match", exc)
                result = local_result
                message = str(exc).lower()
                if "chromadb" in message or "collection" in message:
                    self.vector_rag_available = False
                    logger.warning("[RAG] ChromaDB failure; vector search disabled for session")

        if result is None:
            result = local_result
            logger.info("[RAG] token-match for %r: %s docs returned", query, len(result.documents))

        data = result.model_dump()
        data["method_used"] = method_used
        data["no_relevant_content"] = len(result.documents) == 0
        if hasattr(self.rag_pipeline, "multi_query_generator"):
            data["query_variants"] = self.rag_pipeline.multi_query_generator.generate_queries(
                query,
                num_queries=3,
            )
        else:
            data["query_variants"] = [query]
        data["top_k"] = top_k

        if data["no_relevant_content"] and settings.TAVILY_API_KEY:
            logger.info("[RAG] No relevant content for %r, checking web supplement", query)
            try:
                web_supp = await self.search_service.search(query)
                data["supplemental_web"] = web_supp.model_dump()
                logger.info(
                    "[RAG] Supplemental web search: %s results",
                    len(web_supp.results if hasattr(web_supp, "results") else []),
                )
            except Exception as exc:
                logger.warning("[RAG] Supplemental web search failed: %s", exc)

        confidence = self.confidence_scorer.calculate(query, result.documents) if result.documents else 0.0
        data["confidence"] = confidence
        data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)
        return data

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info("[DEBUG] Executing tool: %s with input: %s", tool_name, tool_input)
        try:
            data: Dict[str, Any]
            if tool_name == "get_price":
                result = await self.market_service.get_price(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "get_history":
                result = await self.market_service.get_history(
                    tool_input["symbol"],
                    days=tool_input.get("days", 30),
                    range_key=tool_input.get("range_key"),
                )
                data = result.model_dump()
            elif tool_name == "get_change":
                result = await self.market_service.get_change(
                    tool_input["symbol"],
                    days=tool_input.get("days", 7),
                    range_key=tool_input.get("range_key"),
                )
                data = result.model_dump()
            elif tool_name == "get_info":
                result = await self.market_service.get_info(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "get_metrics":
                result = await self.market_service.get_metrics(
                    tool_input["symbol"],
                    range_key=tool_input.get("range_key", "1y"),
                )
                data = result.model_dump()
            elif tool_name == "compare_assets":
                result = await self.market_service.compare_assets(
                    tool_input["symbols"],
                    range_key=tool_input.get("range_key", "1y"),
                )
                data = result.model_dump()
            elif tool_name == "search_knowledge":
                data = await self.search_knowledge(tool_input["query"], top_k=tool_input.get("top_k"))
            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
                data = result.model_dump()
            elif tool_name == "search_sec":
                result = await self.sec_service.search(
                    tool_input["query"],
                    symbols=tool_input.get("symbols"),
                )
                data = result.model_dump()
            elif self.plugin_registry and self.plugin_registry.has_plugin(tool_name):
                logger.info("[Plugins] Executing plugin tool: %s", tool_name)
                data = await self.plugin_registry.execute_plugin(tool_name, **tool_input)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            execution_time = time.time() - start_time
            if self.metrics:
                self.metrics.tool_execution_duration.labels(tool=tool_name).observe(execution_time)

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
            logger.error(
                "[DEBUG] Tool execution failed: tool=%s, error=%s",
                tool_name,
                exc,
                exc_info=True,
            )
            if self.metrics:
                self.metrics.tool_errors.labels(tool=tool_name).inc()

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

    async def execute_tools_parallel(self, tool_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        async def execute(step: Dict[str, Any]) -> Dict[str, Any]:
            result = await self.execute_tool(step["name"], step["params"])
            result["step"] = step
            return result

        return await asyncio.gather(*[execute(step) for step in tool_plan])
