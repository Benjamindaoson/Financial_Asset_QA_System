"""Agent core with deterministic routing and grounded response synthesis."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.analysis.technical import TechnicalAnalyzer
from app.analysis.validator import DataValidator
from app.config import settings
from app.core.response_generator import ResponseGenerator
from app.market import MarketDataService
from app.models import SSEEvent, Source, StructuredBlock, ToolResult
from app.models.model_adapter import ModelAdapterFactory
from app.models.multi_model import model_manager
from app.rag.confidence import ConfidenceScorer
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.routing import QueryRoute, QueryRouter, QueryType
from app.search import SECFilingsService, WebSearchService


class ResponseGuard:
    """Validate that numeric claims come from tool payloads."""

    @staticmethod
    def validate(response_text: str, tool_results: List[ToolResult]) -> bool:
        if not response_text.strip():
            return False
        grounded_numbers: set[str] = set()
        for result in tool_results:
            ResponseGuard._collect_numbers(result.data, grounded_numbers)
        if not grounded_numbers:
            return True
        mentioned_numbers = set(re.findall(r"\d+(?:\.\d+)?", response_text))
        return bool(grounded_numbers & mentioned_numbers)

    @staticmethod
    def _collect_numbers(value: Any, bucket: set[str]) -> None:
        if isinstance(value, dict):
            for item in value.values():
                ResponseGuard._collect_numbers(item, bucket)
            return
        if isinstance(value, list):
            for item in value:
                ResponseGuard._collect_numbers(item, bucket)
            return
        if isinstance(value, (int, float)):
            bucket.add(str(int(value)) if float(value).is_integer() else f"{value:.2f}")


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
                logger.info(f"[RAG] Vector search enabled — ChromaDB has {_chroma_count} docs")
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
        self.guard = ResponseGuard()
        self.technical_analyzer = TechnicalAnalyzer()
        self.data_validator = DataValidator()
        self.tools = self._build_tools()
        # ResponseGenerator is enabled only when a DeepSeek API key is configured
        self.response_generator: Optional[ResponseGenerator] = (
            ResponseGenerator() if settings.DEEPSEEK_API_KEY else None
        )

    def _build_tools(self) -> List[Dict[str, Any]]:
        return [
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

    async def _search_knowledge_async(self, query: str) -> Dict[str, Any]:
        """Hybrid vector+reranker retrieval with graceful token-match fallback.

        Flow:
          1. If ChromaDB has docs and models are available → search_grounded() (vector+reranker)
          2. On any model/ChromaDB error → _search_local_documents() (token-match)
          3. If results are empty after threshold filtering → set no_relevant_content=True
          4. When no results + Tavily key present → trigger supplemental web search
        """
        RAG_MIN_SCORE = 0.3
        result = None
        method_used = "token_match"

        if self._vector_rag_available:
            try:
                result = await self.rag_pipeline.search_grounded(query, score_threshold=RAG_MIN_SCORE)
                method_used = "vector+rerank"
                logger.info(
                    f"[RAG] vector+rerank for {query!r}: "
                    f"{len(result.documents)} docs returned (threshold={RAG_MIN_SCORE})"
                )
            except Exception as _vec_err:
                logger.warning(
                    f"[RAG] Vector search failed ({_vec_err}), using token-match for this request"
                )
                # Only permanently disable if it's an infra failure (not a transient model error)
                if "chromadb" in str(_vec_err).lower() or "collection" in str(_vec_err).lower():
                    self._vector_rag_available = False
                    logger.warning("[RAG] ChromaDB failure — vector search disabled for session")

        if result is None:
            result = self.rag_pipeline._search_local_documents(query)
            method_used = "token_match"
            logger.info(
                f"[RAG] token-match for {query!r}: {len(result.documents)} docs returned"
            )

        data = result.model_dump()
        data["method_used"] = method_used
        data["no_relevant_content"] = len(result.documents) == 0

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
        start_time = time.time()
        logger.info(f"[DEBUG] Executing tool: {tool_name} with input: {tool_input}")
        try:
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
                data = await self._search_knowledge_async(tool_input["query"])
            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
                data = result.model_dump()
            elif tool_name == "search_sec":
                result = await self.sec_service.search(tool_input["query"], symbols=tool_input.get("symbols"))
                data = result.model_dump()
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            return {
                "success": True,
                "tool": tool_name,
                "data": data,
                "latency_ms": int((time.time() - start_time) * 1000),
                "status": "success",
                "data_source": data.get("source", tool_name),
                "cache_hit": bool(data.get("cache_hit", False)),
                "error_message": None,
            }
        except Exception as exc:
            logger.error(f"[DEBUG] Tool execution failed: tool={tool_name}, error={str(exc)}", exc_info=True)
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

    async def _build_tool_plan(self, route: QueryRoute) -> List[Dict[str, Any]]:
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
            add_tool("search_knowledge", {"query": route.cleaned_query}, "Searching the knowledge base...")
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
        """Remove YAML frontmatter block (---...---) from document content."""
        t = text.strip()
        if t.startswith("---"):
            end = t.find("---", 3)
            if end != -1:
                return t[end + 3:].strip()
        return t

    def _build_sources(self, tool_results: List[ToolResult]) -> List[Source]:
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
                    rag_context = "知识库中未找到与该问题直接相关的内容"
                    supp_web = result.data.get("supplemental_web")
                    if supp_web:
                        supp_items = supp_web.get("results", [])[:2]
                        if supp_items:
                            supp_lines = "\n".join(
                                f"- {item.get('title', '')}: {item.get('snippet', '')[:150]}"
                                for item in supp_items
                            )
                            rag_context += f"\n\n【补充网络搜索结果】\n{supp_lines}"
                else:
                    rag_context = "\n\n".join(
                        f"[来源: {doc.get('source', '知识库')}]\n"
                        f"{self._strip_frontmatter(doc.get('content', ''))[:500]}"
                        for doc in docs[:3]
                    )
                    rag_relevance = float(result.data.get("confidence", 0.5))
            elif result.tool == "get_price":
                data = result.data
                if data.get("price") is not None:
                    api_data_lines.append(f"当前价格：{data['price']:.2f} {data.get('currency', 'USD')}")
            elif result.tool == "get_change":
                data = result.data
                if data.get("change_pct") is not None:
                    days_n = data.get("days", "N")
                    start = data.get("start_price")
                    end = data.get("end_price")
                    pct = data["change_pct"]
                    trend = data.get("trend", "未知")
                    if start is not None and end is not None:
                        abs_change = end - start
                        api_data_lines.append(
                            f"{days_n}日区间表现：{start:.2f} → {end:.2f}（{abs_change:+.2f}，{pct:+.2f}%）"
                        )
                    else:
                        api_data_lines.append(f"{days_n}日区间涨跌：{pct:+.2f}%")
                    api_data_lines.append(f"近期趋势：{trend}")
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
                        api_data_lines.append(
                            f"最新交易日 OHLCV：开 {last['open']:.2f} / 高 {last.get('high', last['open']):.2f}"
                            f" / 低 {last.get('low', last['open']):.2f} / 收 {last.get('close', last['open']):.2f}"
                        )
                    if last.get("volume"):
                        vol = last["volume"]
                        vol_str = f"{vol / 1e6:.1f}M股" if vol >= 1_000_000 else f"{vol:,.0f}股"
                        api_data_lines.append(f"成交量：{vol_str}")

                    if highs and lows:
                        max_high = max(highs)
                        min_low = min(lows)
                        max_high_idx = highs.index(max_high)
                        min_low_idx = lows.index(min_low)
                        max_high_date = dates[max_high_idx] if max_high_idx < len(dates) else "未知"
                        min_low_date = dates[min_low_idx] if min_low_idx < len(dates) else "未知"
                        days_n = data.get("days", len(hist_points))
                        api_data_lines.append(f"{days_n}日最高：{max_high:.2f}（{max_high_date}）")
                        api_data_lines.append(f"{days_n}日最低：{min_low:.2f}（{min_low_date}）")
            elif result.tool == "get_metrics":
                data = result.data
                if data.get("rsi") is not None:
                    rsi = data["rsi"]
                    if rsi < 30:
                        rsi_zone = "超卖区域（低于30，意味着近期跌幅较大，技术面存在超跌反弹需求，但不代表一定反弹）"
                    elif rsi > 70:
                        rsi_zone = "超买区域（高于70，意味着近期涨幅较大，短期可能面临回调压力）"
                    else:
                        rsi_zone = "中性区域（30-70之间，多空力量相对均衡）"
                    api_data_lines.append(f"RSI(14)：{rsi:.1f}，{rsi_zone}")
                if data.get("max_drawdown_pct") is not None:
                    api_data_lines.append(f"最大回撤：{data['max_drawdown_pct']:+.2f}%（期间最大峰值到谷值的下跌幅度）")
                if data.get("annualized_volatility") is not None:
                    api_data_lines.append(f"年化波动率：{data['annualized_volatility']:.2f}%")
                if data.get("total_return_pct") is not None:
                    api_data_lines.append(f"区间总收益：{data['total_return_pct']:+.2f}%")
            elif result.tool in ("search_web", "search_sec"):
                items = result.data.get("results", [])[:5]
                if result.tool == "search_web":
                    news_items = []
                    for i, item in enumerate(items):
                        title = item.get('title', '未知标题')
                        source = item.get('source', '未知来源')
                        # Prefer full content over snippet; show up to 300 chars
                        content = (item.get('content') or item.get('snippet') or '').strip()
                        snippet = content[:300] if content else "（无详细摘要）"
                        news_items.append(
                            f"新闻{i+1}：{title}\n"
                            f"来源：{source}\n"
                            f"摘要：{snippet}"
                        )
                    news_context = "\n\n".join(news_items) if news_items else ""

        api_completeness = (
            len([r for r in successful if r.tool in market_tools]) / max(len(tool_results), 1)
        )

        api_data_text = "\n".join(api_data_lines) if api_data_lines else "暂无市场数据"
        return api_data_text, rag_context or "暂无知识库检索结果", news_context or "暂无新闻数据", api_completeness, rag_relevance

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
            warnings.append("系统不提供买入、卖出、目标价或个股推荐，只能提供事实数据和风险指标。")
        if validation["level"] == "low":
            warnings.append("以上分析基于公开市场数据，仅供参考，不构成投资建议。")

        comparison = by_tool.get("compare_assets")
        if comparison:
            rows = comparison.get("rows", [])
            best_return = max(rows, key=lambda item: item.get("total_return_pct") or float("-inf"), default=None)
            lowest_drawdown = min(rows, key=lambda item: item.get("max_drawdown_pct") or float("inf"), default=None)
            text = "已完成资产对比。"
            if best_return:
                text += f" {best_return['symbol']} 的区间总收益最高，为 {best_return.get('total_return_pct', 0):+.2f}%。"
            if lowest_drawdown and lowest_drawdown.get("max_drawdown_pct") is not None:
                text += f" 回撤最小的是 {lowest_drawdown['symbol']}，最大回撤 {lowest_drawdown['max_drawdown_pct']:+.2f}%。"
            blocks.append(StructuredBlock(type="table", title="资产对比", data={"columns": ["symbol", "price", "total_return_pct", "annualized_volatility", "max_drawdown_pct"], "rows": rows}))
            blocks.append(StructuredBlock(type="chart", title="对比走势图", data={"chart_type": "comparison", "range_key": comparison.get("range_key"), "series": comparison.get("chart", [])}))
            if warnings:
                blocks.append(StructuredBlock(type="warning", title="风险提示", data={"items": warnings}))
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
            elif days and days <= 90:
                default_range = "3M"
            elif any(kw in query for kw in ["当前", "股价是多少", "现在", "今天", "最新"]):
                default_range = "YTD"
            elif any(kw in query for kw in ["近期", "走势", "最近", "近来"]):
                default_range = "3M"
            else:
                default_range = "1Y"
            blocks.append(StructuredBlock(
                type="chart", title="价格走势图",
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
            }
            if history and history.get("data"):
                last = history["data"][-1]
                km_data.update({
                    "open": last.get("open"),
                    "high": last.get("high"),
                    "low": last.get("low"),
                    "volume": last.get("volume"),
                })
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
            blocks.append(StructuredBlock(type="key_metrics", title="关键数据", data=km_data))
        elif change and change.get("change_pct") is not None:
            km_data = {
                "change_pct": change.get("change_pct"),
                "start_price": change.get("start_price"),
                "end_price": change.get("end_price"),
                "period_days": change.get("days"),
                "trend": change.get("trend"),
                "symbol": change.get("symbol"),
                "currency": "USD",
            }
            if change.get("end_price") is not None and change.get("start_price") is not None:
                km_data["change"] = round(float(change["end_price"]) - float(change["start_price"]), 2)
            blocks.append(StructuredBlock(type="key_metrics", title="关键数据", data=km_data))

        # Block 3: Risk/Return Table
        if metrics and metrics.get("total_return_pct") is not None:
            blocks.append(StructuredBlock(
                type="table", title="收益风险指标",
                data={
                    "columns": ["metric", "value"],
                    "rows": [
                        {"metric": "区间", "value": metrics.get("range_key")},
                        {"metric": "总收益", "value": f"{metrics['total_return_pct']:+.2f}%"},
                        {"metric": "年化波动率", "value": f"{metrics['annualized_volatility']:.2f}%"},
                        {"metric": "最大回撤", "value": f"{metrics['max_drawdown_pct']:+.2f}%"},
                        {"metric": "年化收益", "value": f"{metrics.get('annualized_return_pct', 0):+.2f}%"},
                        {"metric": "Sharpe", "value": f"{metrics.get('sharpe_ratio', 0):.2f}" if metrics.get("sharpe_ratio") is not None else "N/A"},
                    ],
                },
            ))

        # Block 4: Knowledge Quote (KNOWLEDGE / HYBRID routes only)
        if knowledge and knowledge.get("documents"):
            if route.query_type in (QueryType.KNOWLEDGE, QueryType.HYBRID):
                docs = knowledge["documents"][:3]
                preview_lines = [
                    f"- {self._strip_frontmatter(doc['content'])[:120].strip()}"
                    for doc in docs
                ]
                blocks.append(StructuredBlock(
                    type="quote", title="知识库摘录",
                    data={"text": "\n".join(preview_lines)}
                ))

        # Block 5: News / SEC fallback bullets (removed when LLM succeeds)
        if sec_results and sec_results.get("results"):
            blocks.append(StructuredBlock(
                type="bullets", title="SEC/财报来源",
                data={"items": [
                    f"{item.get('title')} ({item.get('published') or 'unknown'})"
                    for item in sec_results["results"][:3]
                ]}
            ))
        if web_results and web_results.get("results"):
            blocks.append(StructuredBlock(
                type="bullets", title="相关新闻",
                data={"items": [
                    item.get("title") for item in web_results["results"][:3]
                    if item.get("title")
                ]}
            ))

        if warnings:
            blocks.append(StructuredBlock(type="warning", title="风险提示", data={"items": warnings}))

        # Template fallback text (replaced by LLM analysis when available)
        fragments: List[str] = []
        if price and price.get("price") is not None:
            fragments.append(
                f"{price['symbol']} 最新价格 {price['price']:.2f} {price.get('currency') or ''}".strip()
            )
        if change and change.get("change_pct") is not None:
            fragments.append(f"{change.get('days', 7)}日涨跌 {change['change_pct']:+.2f}%")
        if knowledge and not price and not change and not metrics:
            docs = knowledge.get("documents", [])
            if docs:
                first_doc = self._strip_frontmatter(docs[0]["content"]).replace("\n", " ")
                fragments = [first_doc[:140].strip()]
        if fragments:
            return "；".join(fragments) + "。", blocks
        return "已完成数据检索，正在生成分析...", blocks

    async def run(self, query: str, model_name: Optional[str] = None) -> AsyncGenerator[SSEEvent, None]:
        request_id = str(uuid.uuid4())
        tool_results: List[ToolResult] = []
        model_name = model_name or self._select_model(query)
        model_config = self.model_manager.models.get(model_name)
        if model_name and model_name not in self.model_manager.models:
            yield SSEEvent(type="error", message=f"Model {model_name} not found", code="MODEL_NOT_FOUND")
            return

        logger.info(f"[DEBUG] AgentCore.run() called with query: {query}")
        yield SSEEvent(type="model_selected", model=model_name, provider=getattr(model_config, "provider", "deepseek"), complexity=self.model_manager.classify_query(query))
        route = await self.query_router.classify_async(query)
        logger.info(f"[DEBUG] Route: type={route.query_type}, requires_knowledge={route.requires_knowledge}")

        if route.refuses_advice:
            refusal = "我不能给出买入、卖出、目标价或个股推荐。你可以继续问我该标的的价格、历史走势、波动率、最大回撤或最新公告。"
            yield SSEEvent(type="chunk", text=refusal)
            yield SSEEvent(type="done", verified=True, sources=[], request_id=request_id, model=model_name, tokens_input=len(query) // 4, tokens_output=len(refusal) // 4, data={"confidence": {"level": "high", "score": 100}, "blocks": [StructuredBlock(type="warning", title="合规提示", data={"items": ["系统不提供投资建议，仅提供事实数据、知识解释和风险指标。"]}).model_dump()], "route": {"type": route.query_type.value, "symbols": route.symbols}, "disclaimer": "以上内容仅供参考，不构成投资建议。"})
            return

        try:
            tool_plan = await self._build_tool_plan(route)
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
                fallback = self.data_validator.get_fallback_message(validation, route.symbols[0] if route.symbols else "当前问题")
                yield SSEEvent(type="chunk", text=fallback)
                yield SSEEvent(type="done", verified=False, sources=sources, request_id=request_id, model=model_name, tokens_input=len(query) // 4, tokens_output=len(fallback) // 4, data={"confidence": {"level": validation["level"], "score": validation["confidence"]}, "blocks": [StructuredBlock(type="warning", title="数据不足", data={"items": validation["missing"]}).model_dump()], "route": {"type": route.query_type.value, "symbols": route.symbols, "range_key": route.range_key}, "disclaimer": "以上内容仅供参考，不构成投资建议。"})
                return

            technical_analysis = None
            for result in tool_results:
                if result.tool == "get_history" and len(result.data.get("data", [])) >= 20:
                    from app.models import PricePoint

                    technical_analysis = self.technical_analyzer.analyze([PricePoint(**item) for item in result.data["data"]])
                    break

            # _compose_answer generates structured blocks (charts/tables) + a template fallback text
            template_text, blocks = self._compose_answer(query, route, tool_results, technical_analysis, validation)

            # Push the template summary text first (hidden by frontend when analysis block exists)
            yield SSEEvent(type="chunk", text=template_text)

            # Attempt LLM-based analysis generation as a separate structured block
            llm_used = False
            if self.response_generator and settings.DEEPSEEK_API_KEY:
                try:
                    yield SSEEvent(type="tool_start", name="llm_generate", display="正在生成 AI 分析...")
                    api_data, rag_context, news_context, api_completeness, rag_relevance = self._build_llm_context(tool_results)
                    # Enrich api_data with locally-computed technical indicators
                    if technical_analysis and not technical_analysis.get("error"):
                        tech_lines = []
                        rsi = technical_analysis.get("rsi")
                        if rsi is not None:
                            if rsi < 30:
                                rsi_zone = "超卖区域（低于30，近期跌幅较大，存在超跌反弹需求）"
                            elif rsi > 70:
                                rsi_zone = "超买区域（高于70，近期涨幅较大，短期可能面临回调压力）"
                            else:
                                rsi_zone = "中性区域（30-70之间，多空力量相对均衡）"
                            tech_lines.append(f"RSI(14)：{rsi:.1f}，{rsi_zone}")
                        if technical_analysis.get("max_drawdown_pct") is not None:
                            tech_lines.append(f"最大回撤：{technical_analysis['max_drawdown_pct']:+.2f}%（期间最大峰値到谷値的下跌幅度）")
                        if technical_analysis.get("trend"):
                            tech_lines.append(f"走势判断：{technical_analysis['trend']}")
                        if tech_lines:
                            api_data = api_data + "\n\n技术指标：\n" + "\n".join(tech_lines)

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
                        # Add LLM analysis as a structured block
                        blocks.append(StructuredBlock(
                            type="analysis",
                            title="AI 分析",
                            data={"text": llm_text.strip()}
                        ))
                        llm_used = True
                        # When LLM analysis succeeded, remove redundant fallback blocks
                        blocks = [b for b in blocks if b.type not in ("bullets", "warning")]
                        logger.info(f"[LLM] Analysis generated successfully ({len(llm_text)} chars)")
                except asyncio.TimeoutError:
                    logger.warning("[LLM] Generator timed out, skipping AI analysis")
                except Exception as llm_exc:
                    logger.warning(f"[LLM] Generator failed ({llm_exc}), skipping AI analysis")

            self.model_manager.record_usage(model_name=model_name, tokens_input=len(query) // 4, tokens_output=len(template_text) // 4, success=True)
            yield SSEEvent(type="done", verified=self.guard.validate(template_text, tool_results), sources=sources, request_id=request_id, model=model_name, tokens_input=len(query) // 4, tokens_output=len(template_text) // 4, data={"confidence": {"level": validation["level"], "score": validation["confidence"]}, "blocks": [block.model_dump() for block in blocks], "route": {"type": route.query_type.value, "symbols": route.symbols, "range_key": route.range_key}, "llm_used": llm_used, "disclaimer": "以上内容仅供参考，不构成投资建议。"})
        except Exception as exc:
            self.model_manager.record_usage(model_name=model_name, tokens_input=len(query) // 4, tokens_output=0, success=False)
            yield SSEEvent(type="error", message=str(exc), code="LLM_ERROR", model=model_name)

    def get_available_models(self) -> List[Dict[str, Any]]:
        return self.model_manager.list_models()

    def get_usage_report(self) -> Dict[str, Any]:
        return self.model_manager.get_usage_report()
