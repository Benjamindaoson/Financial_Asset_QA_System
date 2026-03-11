"""Agent core with deterministic routing and grounded response synthesis."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.analysis.technical import TechnicalAnalyzer
from app.analysis.validator import DataValidator
from app.market import MarketDataService
from app.models import SSEEvent, Source, StructuredBlock, ToolResult
from app.models.model_adapter import ModelAdapterFactory  # Backward-compatible import for tests.
from app.models.multi_model import model_manager
from app.rag.confidence import ConfidenceScorer
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.routing import QueryRoute, QueryRouter, QueryType
from app.routing.llm_router import LLMQueryRouter
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
        if isinstance(value, int):
            bucket.add(str(value))
            return
        if isinstance(value, float):
            bucket.add(str(value))
            bucket.add(f"{value:.2f}")


class AgentCore:
    """Grounded financial QA agent."""

    DEGRADED_MODEL_ID = "degraded-local"
    DEGRADED_NOTE = "LLM分析不可用，以下为知识库检索结果。"

    def __init__(self, preferred_model: Optional[str] = None, use_llm_routing: bool = True):
        self.model_manager = model_manager
        self.preferred_model = preferred_model
        self.use_llm_routing = use_llm_routing
        self.market_service = MarketDataService()
        self.rag_pipeline = HybridRAGPipeline()
        self.confidence_scorer = ConfidenceScorer()
        self.search_service = WebSearchService()
        self.sec_service = SECFilingsService()
        self.query_router = QueryRouter()
        self.llm_router = LLMQueryRouter()  # New LLM-based router
        self.guard = ResponseGuard()
        self.technical_analyzer = TechnicalAnalyzer()
        self.data_validator = DataValidator()
        self.tools = self._build_tools()

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

    def is_degraded_mode(self) -> bool:
        return self.model_manager.is_degraded_mode()

    async def _search_knowledge_degraded(self, query: str):
        return await self.rag_pipeline.search(query, use_hybrid=True)

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any], degraded_mode: bool = False) -> Dict[str, Any]:
        start_time = time.time()
        try:
            if tool_name == "get_price":
                result = await self.market_service.get_price(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "get_history":
                kwargs = {"days": tool_input.get("days", 30)}
                if tool_input.get("range_key"):
                    kwargs["range_key"] = tool_input["range_key"]
                result = await self.market_service.get_history(tool_input["symbol"], **kwargs)
                data = result.model_dump()
            elif tool_name == "get_change":
                kwargs = {"days": tool_input.get("days", 7)}
                if tool_input.get("range_key"):
                    kwargs["range_key"] = tool_input["range_key"]
                result = await self.market_service.get_change(tool_input["symbol"], **kwargs)
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
                result = await self._search_knowledge_degraded(tool_input["query"]) if degraded_mode else await self.rag_pipeline.search(tool_input["query"], use_hybrid=True)
                confidence = self.confidence_scorer.calculate(tool_input["query"], result.documents) if result.documents else 0.0
                data = result.model_dump()
                data["confidence"] = confidence
                data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)
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

    async def _execute_tools_parallel(self, tool_plan: List[Dict[str, Any]], degraded_mode: bool = False) -> List[Dict[str, Any]]:
        async def execute(step: Dict[str, Any]) -> Dict[str, Any]:
            result = await self._execute_tool(step["name"], step["params"], degraded_mode=degraded_mode)
            result["step"] = step
            return result

        return await asyncio.gather(*[execute(step) for step in tool_plan])

    def _select_model(self, query: str) -> str:
        if self.preferred_model and self.preferred_model in self.model_manager.models:
            return self.preferred_model
        complexity = self.model_manager.classify_query(query)
        selected = self.model_manager.select_model(complexity)
        if selected:
            return selected
        if self.model_manager.is_degraded_mode():
            return self.DEGRADED_MODEL_ID
        return "deepseek-chat"

    async def _build_tool_plan(self, route: QueryRoute) -> List[Dict[str, Any]]:
        plan: List[Dict[str, Any]] = []

        def add_tool(name: str, params: Dict[str, Any], display: str) -> None:
            plan.append({"name": name, "params": params, "display": display})

        primary_symbol = route.symbols[0] if route.symbols else None
        days = route.days or 30
        range_key = route.range_key

        if route.requires_comparison and len(route.symbols) >= 2:
            add_tool("compare_assets", {"symbols": route.symbols[:4], "range_key": range_key or "1y"}, f"正在对比 {', '.join(route.symbols[:4])} 的表现...")
            return plan

        if route.query_type in {QueryType.MARKET, QueryType.HYBRID} and primary_symbol:
            if route.requires_price:
                add_tool("get_price", {"symbol": primary_symbol}, f"正在获取 {primary_symbol} 的最新价格...")
            if route.requires_change:
                change_params = {"symbol": primary_symbol, "days": route.days or 7}
                if range_key:
                    change_params["range_key"] = range_key
                add_tool("get_change", change_params, f"正在计算 {primary_symbol} 的涨跌幅...")
            if route.requires_history:
                history_params = {"symbol": primary_symbol, "days": days}
                if range_key:
                    history_params["range_key"] = range_key
                add_tool("get_history", history_params, f"正在加载 {primary_symbol} 的历史走势...")
            if route.requires_info:
                add_tool("get_info", {"symbol": primary_symbol}, f"正在获取 {primary_symbol} 的基础信息...")
            if route.requires_metrics:
                add_tool("get_metrics", {"symbol": primary_symbol, "range_key": range_key or "1y"}, f"正在计算 {primary_symbol} 的风险指标...")

        if route.requires_knowledge:
            add_tool("search_knowledge", {"query": route.cleaned_query}, "正在检索金融知识库...")
        if route.requires_web:
            add_tool("search_web", {"query": route.cleaned_query}, "正在检索最新市场新闻...")
        if route.requires_sec:
            add_tool("search_sec", {"query": route.cleaned_query, "symbols": route.symbols}, "正在检索 SEC 公告...")
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

    def _compose_answer(
        self,
        query: str,
        route: QueryRoute,
        tool_results: List[ToolResult],
        technical_analysis: Optional[Dict[str, Any]],
        validation: Dict[str, Any],
        degraded_mode: bool = False,
    ) -> tuple[str, List[StructuredBlock]]:
        by_tool = {result.tool: result.data for result in tool_results if result.status == "success"}
        blocks: List[StructuredBlock] = []
        warnings: List[str] = []

        if route.refuses_advice:
            warnings.append("系统不提供买入、卖出、推荐或目标价建议，只提供事实数据和风险指标。")
        if validation["level"] == "low":
            warnings.append("当前结论基于有限数据，建议交叉验证后再使用。")

        comparison = by_tool.get("compare_assets")
        if comparison:
            rows = comparison.get("rows", [])
            best_return = max(rows, key=lambda item: item.get("total_return_pct") or float("-inf"), default=None)
            lowest_drawdown = min(rows, key=lambda item: item.get("max_drawdown_pct") or float("inf"), default=None)
            parts = ["已完成资产对比。"]
            if best_return and best_return.get("total_return_pct") is not None:
                parts.append(f"{best_return['symbol']} 的区间总收益最高，为 {best_return['total_return_pct']:+.2f}%。")
            if lowest_drawdown and lowest_drawdown.get("max_drawdown_pct") is not None:
                parts.append(f"{lowest_drawdown['symbol']} 的最大回撤最小，为 {lowest_drawdown['max_drawdown_pct']:+.2f}%。")
            blocks.append(StructuredBlock(type="table", title="资产对比", data={"columns": ["symbol", "price", "total_return_pct", "annualized_volatility", "max_drawdown_pct"], "rows": rows}))
            blocks.append(StructuredBlock(type="chart", title="对比走势", data={"chart_type": "comparison", "range_key": comparison.get("range_key"), "series": comparison.get("chart", [])}))
            if warnings:
                blocks.append(StructuredBlock(type="warning", title="风险提示", data={"items": warnings}))
            return " ".join(parts), blocks

        fragments: List[str] = []
        bullet_items: List[str] = []
        price = by_tool.get("get_price")
        change = by_tool.get("get_change")
        metrics = by_tool.get("get_metrics")
        history = by_tool.get("get_history")
        info = by_tool.get("get_info")
        knowledge = by_tool.get("search_knowledge")
        sec_results = by_tool.get("search_sec")
        web_results = by_tool.get("search_web")

        if price and price.get("price") is not None:
            fragments.append(f"{price['symbol']} 最新价格为 {price['price']:.2f} {price.get('currency') or ''}".strip())
            bullet_items.append(f"最新价格：{price['price']:.2f} {price.get('currency') or ''}".strip())
        if change and change.get("change_pct") is not None:
            fragments.append(f"区间涨跌幅为 {change['change_pct']:+.2f}%")
            bullet_items.append(f"区间涨跌幅：{change['change_pct']:+.2f}%")
        if metrics and metrics.get("total_return_pct") is not None:
            fragments.append(
                f"{metrics.get('range_key', '1y')} 总收益 {metrics['total_return_pct']:+.2f}%，"
                f" 波动率 {metrics['annualized_volatility']:.2f}%，"
                f" 最大回撤 {metrics['max_drawdown_pct']:+.2f}%"
            )
            blocks.append(
                StructuredBlock(
                    type="table",
                    title="收益与风险指标",
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
                )
            )
        if history and history.get("data"):
            blocks.append(StructuredBlock(type="chart", title="价格走势", data={"chart_type": "history", "symbol": history["symbol"], "range_key": history.get("range_key"), "series": history.get("data", [])}))
            if technical_analysis and not technical_analysis.get("error"):
                bullet_items.extend(
                    [
                        f"趋势：{technical_analysis.get('trend')}",
                        f"RSI：{technical_analysis.get('rsi')}",
                        f"最大回撤：{technical_analysis.get('max_drawdown_pct'):+.2f}%" if technical_analysis.get("max_drawdown_pct") is not None else "最大回撤：N/A",
                    ]
                )
        if info and info.get("name"):
            bullet_items.append(f"标的名称：{info.get('name')}")
            if info.get("pe_ratio") is not None:
                bullet_items.append(f"市盈率：{info['pe_ratio']:.2f}")
        if knowledge and knowledge.get("documents"):
            docs = knowledge["documents"][:3]
            quote_lines = []
            for doc in docs:
                parts = [part for part in [doc.get("title"), doc.get("section"), doc.get("source")] if part]
                label = " / ".join(parts)
                snippet = doc["content"][:180].strip()
                quote_lines.append(f"- [{label}] {snippet}" if label else f"- {snippet}")
            blocks.append(StructuredBlock(type="quote", title="知识库摘录", data={"text": "\n".join(quote_lines)}))
            if degraded_mode:
                fragments = [self.DEGRADED_NOTE, "\n".join(quote_lines)]
            elif not price and not change and not metrics:
                fragments = [docs[0]["content"].replace("\n", " ")[:180].strip()]
            else:
                fragments.append("已结合知识库对相关概念进行补充说明。")
        if sec_results and sec_results.get("results"):
            blocks.append(StructuredBlock(type="bullets", title="SEC/财报来源", data={"items": [f"{item.get('title')} ({item.get('published') or 'unknown'})" for item in sec_results["results"][:3]]}))
            fragments.append("已补充 SEC 公告和财报来源。")
        if web_results and web_results.get("results"):
            blocks.append(StructuredBlock(type="bullets", title="相关新闻", data={"items": [item.get("title") for item in web_results["results"][:3] if item.get("title")]}))
            fragments.append("已补充外部新闻背景。")

        if bullet_items:
            blocks.insert(0, StructuredBlock(type="bullets", title="要点", data={"items": bullet_items}))
        if warnings:
            blocks.append(StructuredBlock(type="warning", title="风险提示", data={"items": warnings}))
        if fragments:
            return "。".join(fragment.strip("。") for fragment in fragments if fragment) + "。", blocks
        return f"已完成对“{query}”的检索，但当前可用数据有限。", blocks

    async def run(self, query: str, model_name: Optional[str] = None) -> AsyncGenerator[SSEEvent, None]:
        request_id = str(uuid.uuid4())
        tool_results: List[ToolResult] = []
        degraded_mode = self.is_degraded_mode()
        selected_model = model_name or self._select_model(query)

        if degraded_mode:
            selected_model = self.DEGRADED_MODEL_ID
            model_config = None
        else:
            model_config = self.model_manager.models.get(selected_model)
            if selected_model and selected_model not in self.model_manager.models:
                yield SSEEvent(type="error", message=f"Model {selected_model} not found", code="MODEL_NOT_FOUND")
                return

        yield SSEEvent(
            type="model_selected",
            model=selected_model,
            provider=getattr(model_config, "provider", "local" if degraded_mode else "deepseek"),
            complexity=self.model_manager.classify_query(query),
        )

        # Use LLM routing if enabled and available
        if self.use_llm_routing and not degraded_mode:
            llm_route = await self.llm_router.route(query)
            # Convert LLM route to tool plan
            tool_plan = llm_route.tools_to_call
            route = None  # We'll skip the old route-based logic
        else:
            # Fallback to rule-based routing
            route = await self.query_router.classify_async(query)
            tool_plan = None

        # Handle advice refusal (only for rule-based routing)
        if route and route.refuses_advice is True:
            refusal = "我不能提供买入、卖出、推荐或目标价建议。你可以继续询问价格、历史走势、波动率、最大回撤或最新公告。"
            yield SSEEvent(type="chunk", text=refusal)
            yield SSEEvent(
                type="done",
                verified=True,
                sources=[],
                request_id=request_id,
                model=selected_model,
                tokens_input=len(query) // 4,
                tokens_output=len(refusal) // 4,
                data={
                    "confidence": {"level": "high", "score": 100},
                    "blocks": [StructuredBlock(type="warning", title="合规提示", data={"items": ["系统不提供投资建议，仅提供事实数据、知识解释和风险指标。"]}).model_dump()],
                    "route": {"type": route.query_type.value, "symbols": route.symbols},
                    "disclaimer": "以上内容仅供参考，不构成投资建议。",
                },
            )
            return

        try:
            # Build tool plan based on routing method
            if tool_plan is None:
                tool_plan = await self._build_tool_plan(route)

            for step in tool_plan:
                yield SSEEvent(type="tool_start", name=step["name"], display=step["display"])

            raw_results = await self._execute_tools_parallel(tool_plan, degraded_mode=degraded_mode) if tool_plan else []
            for raw_result in raw_results:
                if not raw_result["success"]:
                    continue
                tool_result = self._normalize_tool_result(raw_result)
                tool_results.append(tool_result)
                yield SSEEvent(type="tool_data", tool=raw_result["tool"], data=raw_result["data"])

            validation = self.data_validator.validate_tool_results(tool_results)
            sources = self._build_sources(tool_results)

            # Extract symbols from tool results if route is None (LLM routing)
            symbols = []
            if route:
                symbols = route.symbols
            else:
                # Extract from tool results
                for result in tool_results:
                    if result.tool in ["get_price", "get_history", "get_info", "get_metrics"]:
                        symbol = result.data.get("symbol")
                        if symbol and symbol not in symbols:
                            symbols.append(symbol)

            if self.data_validator.should_block_response(validation):
                fallback = self.data_validator.get_fallback_message(validation, symbols[0] if symbols else "当前问题")
                yield SSEEvent(type="chunk", text=fallback)
                yield SSEEvent(
                    type="done",
                    verified=False,
                    sources=sources,
                    request_id=request_id,
                    model=selected_model,
                    tokens_input=len(query) // 4,
                    tokens_output=len(fallback) // 4,
                    data={
                        "confidence": {"level": validation["level"], "score": validation["confidence"]},
                        "blocks": [StructuredBlock(type="warning", title="数据不足", data={"items": validation["missing"]}).model_dump()],
                        "route": {"type": route.query_type.value if route else "llm", "symbols": symbols, "range_key": route.range_key if route else None},
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

            # For LLM routing, create a minimal route object for _compose_answer
            if route is None:
                from app.routing import QueryRoute, QueryType
                route = QueryRoute(
                    query_type=QueryType.HYBRID,
                    cleaned_query=query,
                    symbols=symbols,
                    requires_knowledge=any(r.tool == "search_knowledge" for r in tool_results),
                    requires_web=any(r.tool == "search_web" for r in tool_results)
                )

            final_text, blocks = self._compose_answer(
                query,
                route,
                tool_results,
                technical_analysis,
                validation,
                degraded_mode=degraded_mode,
            )
            yield SSEEvent(type="chunk", text=final_text)

            self.model_manager.record_usage(model_name=selected_model, tokens_input=len(query) // 4, tokens_output=len(final_text) // 4, success=True)
            yield SSEEvent(
                type="done",
                verified=self.guard.validate(final_text, tool_results),
                sources=sources,
                request_id=request_id,
                model=selected_model,
                tokens_input=len(query) // 4,
                tokens_output=len(final_text) // 4,
                data={
                    "confidence": {"level": validation["level"], "score": validation["confidence"]},
                    "blocks": [block.model_dump() for block in blocks],
                    "route": {"type": route.query_type.value, "symbols": route.symbols, "range_key": route.range_key},
                    "disclaimer": "以上内容仅供参考，不构成投资建议。",
                    "degraded_mode": degraded_mode,
                },
            )
        except Exception as exc:
            self.model_manager.record_usage(model_name=selected_model, tokens_input=len(query) // 4, tokens_output=0, success=False)
            yield SSEEvent(type="error", message=str(exc), code="LLM_ERROR", model=selected_model)

    def get_available_models(self) -> List[Dict[str, Any]]:
        return self.model_manager.list_models()

    def get_usage_report(self) -> Dict[str, Any]:
        return self.model_manager.get_usage_report()
