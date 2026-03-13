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
from app.config import get_prompt, settings
from app.market import MarketDataService
from app.models import Document, KnowledgeResult, SSEEvent, Source, StructuredBlock, ToolResult
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

        mentioned_numbers = ResponseGuard._extract_relevant_numbers(response_text)
        if not mentioned_numbers:
            return True

        return all(ResponseGuard._is_grounded(number, grounded_numbers) for number in mentioned_numbers)

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

    @staticmethod
    def _extract_relevant_numbers(text: str) -> List[float]:
        values: List[float] = []
        for match in re.finditer(r"\d+(?:\.\d+)?", text):
            token = match.group(0)
            number = float(token)
            if number < 10 and "." not in token:
                continue
            values.append(number)
        return values

    @staticmethod
    def _is_grounded(number: float, grounded_numbers: set[str], tolerance: float = 0.005) -> bool:
        for grounded in grounded_numbers:
            try:
                grounded_value = float(grounded)
            except ValueError:
                continue
            if abs(number - grounded_value) <= tolerance:
                return True
        return False


class AgentCore:
    """
    Grounded financial QA agent (Pipeline Orchestrator).
    
    [架构设计意图 - Architecture Intent]
    本类不采用传统的 ReAct Agent 模式（易产生死循环与幻觉），而是采用了
    确定性的多阶段流水线 (Multi-Stage DAG Pipeline)：
    1. Intent Routing (意图路由)：判断查询性质（行情、计算、知识检索）。
    2. Stage Execution (阶段执行)：并发调用对应的外部工具（API、RAG）。
    3. Validation & Synthesis (校验与合成)：提取客观证据，拦截违规要求，
       最后交由 LLM 进行无格式文本总结输出。
       
    这种设计保证了金融场景下的：1. 极高容错率 2. 数据100%客观不编造 3. 流式响应速度。
    """

    DEGRADED_MODEL_ID = "degraded-local"
    DEGRADED_NOTE = "当前处于降级模式：仅基于已检索到的客观资料作答（无LLM分析）。"

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
        self.llm_router = LLMQueryRouter()
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

    async def _search_knowledge_degraded(self, query: str) -> KnowledgeResult:
        return await self.rag_pipeline.search(query, use_hybrid=True)

    @staticmethod
    def _build_knowledge_metadata_filter(tool_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        metadata_filter: Dict[str, Any] = {}
        source_type = tool_input.get("source_type")
        if source_type:
            metadata_filter["source_type"] = source_type

        symbols = tool_input.get("symbols") or []
        if symbols:
            metadata_filter["asset_code"] = symbols[0] if len(symbols) == 1 else list(symbols)

        date_prefix = tool_input.get("date")
        if date_prefix:
            metadata_filter["date"] = date_prefix

        return metadata_filter or None

    @staticmethod
    def _external_results_to_documents(results: List[Dict[str, Any]], source_type: str) -> List[Document]:
        documents: List[Document] = []
        for index, item in enumerate(results[:5]):
            title = item.get("title") or source_type.upper()
            snippet = item.get("snippet") or ""
            published = item.get("published")
            url = item.get("url")
            content_parts = [title]
            if published:
                content_parts.append(f"Date: {published}")
            if snippet:
                content_parts.append(snippet)

            documents.append(
                Document(
                    content="\n".join(content_parts).strip(),
                    source=item.get("source") or source_type,
                    score=max(0.35, 0.6 - index * 0.05),
                    title=title,
                    section=published,
                    chunk_id=f"{source_type}:{index}:{title[:24]}",
                    retrieval_stage=f"{source_type}_fallback",
                    metadata={
                        "source_type": source_type,
                        "url": url,
                        "published": published,
                        "external": True,
                        "chunk_type": "external",
                    },
                )
            )
        return documents

    async def _search_knowledge(self, tool_input: Dict[str, Any], degraded_mode: bool = False) -> KnowledgeResult:
        query = tool_input["query"]
        logger.info(f"[RAG Step 1] _search_knowledge called with query: {query}")
        metadata_filter = self._build_knowledge_metadata_filter(tool_input)

        if degraded_mode:
            logger.info("[RAG Step 2] Using degraded mode")
            base_result = await self._search_knowledge_degraded(query)
        else:
            logger.info("[RAG Step 2] Calling rag_pipeline.search with use_hybrid=True")
            try:
                base_result = await self.rag_pipeline.search(query, use_hybrid=True, metadata_filter=metadata_filter)
                logger.info(f"[RAG Step 3] rag_pipeline.search returned {len(base_result.documents)} documents")
            except Exception as e:
                logger.error(f"[RAG Step 3 ERROR] rag_pipeline.search failed: {e}", exc_info=True)
                raise

        base_documents = list(base_result.documents)
        confidence = self.confidence_scorer.calculate(query, base_documents) if base_documents else 0.0
        logger.info(f"[RAG Step 4] Confidence calculated: {confidence}")

        include_web_fallback = bool(tool_input.get("include_web_fallback"))
        include_sec_fallback = bool(tool_input.get("include_sec_fallback"))
        should_expand = include_web_fallback or include_sec_fallback
        if not should_expand:
            logger.info(f"[RAG Step 5] Returning base result with {len(base_documents)} documents")
            return base_result

        combined_documents = list(base_documents)

        if include_web_fallback:
            web_result = await self.search_service.search(query)
            combined_documents.extend(self._external_results_to_documents([item.model_dump() for item in web_result.results], "web"))

        if include_sec_fallback:
            sec_result = await self.sec_service.search(query, symbols=tool_input.get("symbols"))
            combined_documents.extend(self._external_results_to_documents([item.model_dump() for item in sec_result.results], "sec"))

        if not combined_documents:
            return base_result

        try:
            reranked_documents = self.rag_pipeline.rerank_documents(query, combined_documents)
        except Exception:
            reranked_documents = sorted(combined_documents, key=lambda item: item.score, reverse=True)
        return KnowledgeResult(
            documents=reranked_documents[: max(settings.RAG_TOP_N, 4)],
            total_found=len(reranked_documents),
            query=query,
            retrieval_meta={
                "strategy": "hybrid_with_fallback",
                "metadata_filter": metadata_filter,
                "base_documents": len(base_documents),
                "fallback_used": should_expand,
            },
        )

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
                logger.info(f"[Tool Execution] Starting search_knowledge with input: {tool_input}")
                result = await self._search_knowledge(tool_input, degraded_mode=degraded_mode)
                logger.info(f"[Tool Execution] search_knowledge completed, documents: {len(result.documents)}")
                confidence = self.confidence_scorer.calculate(tool_input["query"], result.documents) if result.documents else 0.0
                data = result.model_dump()
                data["confidence"] = confidence
                data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)
                logger.info(f"[Tool Execution] Final data keys: {list(data.keys())}, documents count: {len(data.get('documents', []))}")
            elif tool_name == "search_web":
                result = await self.search_service.search(
                    tool_input["query"],
                    symbols=tool_input.get("symbols"),
                    context=tool_input.get("context")
                )
                data = result.model_dump()
            elif tool_name == "search_sec":
                symbol = tool_input.get("symbol")
                query = tool_input.get("query", f"Earnings Report {tool_input.get('quarter', '')}")
                symbols = tool_input.get("symbols") or ([symbol] if symbol else None)
                result = await self.sec_service.search(query, symbols=symbols)
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

    async def _build_tool_plan(self, route: QueryRoute) -> List[List[Dict[str, Any]]]:
        """Builds a multi-stage tool execution plan (DAG)."""
        logger.info(f"[_build_tool_plan] START - route type: {route.query_type}, requires_knowledge: {route.requires_knowledge}")
        stages: List[List[Dict[str, Any]]] = [[], []]

        def add_tool(name: str, params: Dict[str, Any], display: str, stage: int = 0) -> None:
            logger.info(f"[_build_tool_plan] Adding tool: {name} to stage {stage}")
            stages[stage].append({"name": name, "params": params, "display": display})

        primary_symbol = route.symbols[0] if route.symbols else None
        days = route.days or 30
        range_key = route.range_key

        if route.requires_comparison and len(route.symbols) >= 2:
            add_tool("compare_assets", {"symbols": route.symbols[:4], "range_key": range_key or "1y"}, f"对比标的：{', '.join(route.symbols[:4])}…", stage=0)
            return [stages[0]]

        if route.query_type in {QueryType.MARKET, QueryType.HYBRID} and primary_symbol:
            if route.requires_price:
                add_tool("get_price", {"symbol": primary_symbol}, f"获取最新价格：{primary_symbol}…", stage=0)
            if route.requires_change:
                change_params = {"symbol": primary_symbol, "days": route.days or 7}
                if range_key:
                    change_params["range_key"] = range_key
                add_tool("get_change", change_params, f"计算区间涨跌：{primary_symbol}…", stage=0)
            if route.requires_history:
                history_params = {"symbol": primary_symbol, "days": days}
                if range_key:
                    history_params["range_key"] = range_key
                add_tool("get_history", history_params, f"加载历史行情：{primary_symbol}…", stage=0)
            if route.requires_info:
                add_tool("get_info", {"symbol": primary_symbol}, f"获取标的概况：{primary_symbol}…", stage=0)
            if route.requires_metrics:
                add_tool("get_metrics", {"symbol": primary_symbol, "range_key": range_key or "1y"}, f"计算风险指标：{primary_symbol}…", stage=0)

        if route.requires_knowledge:
            add_tool("search_knowledge", {"query": route.cleaned_query, "date": route.date}, "检索知识库…", stage=1)
        if route.requires_web:
            add_tool("search_web", {"query": route.cleaned_query, "date": route.date}, "检索市场新闻…", stage=1)
        if route.requires_sec:
            add_tool("search_sec", {"query": route.cleaned_query, "symbols": route.symbols, "date": route.date}, "检索 SEC/财报公告…", stage=1)

        # Filter out empty stages and ensure search tools have symbols
        final_stages = []
        for stage in stages:
            if not stage: continue
            for step in stage:
                if step["name"] == "search_knowledge":
                    step["params"].setdefault("symbols", route.symbols)
                    step["params"].setdefault("include_web_fallback", route.requires_web)
                    step["params"].setdefault("include_sec_fallback", route.requires_sec)
                    if route.report_focus:
                        step["params"]["source_type"] = "report"
            final_stages.append(stage)

        logger.info(f"[_build_tool_plan] COMPLETE - {len(final_stages)} stages, tools: {[[s['name'] for s in stage] for stage in final_stages]}")
        return final_stages

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
                metadata = doc.get("metadata") or {}
                doc_name = doc.get("title") or doc.get("source", result.tool)
                doc_timestamp = metadata.get("published") or metadata.get("date") or payload.get("timestamp") or datetime.utcnow().isoformat()
                doc_url = metadata.get("url")
                key = (doc_name, doc_timestamp, doc_url)
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1], url=key[2]))
                    seen.add(key)
        return sources

    @staticmethod
    def _clean_knowledge_text(text: str) -> str:
        cleaned = re.sub(r"(?m)^\s*#+\s*", "", text or "")
        cleaned = re.sub(r"(?m)^\s*[-*]\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _summarize_knowledge_documents(self, query: str, docs: List[Dict[str, Any]]) -> List[str]:
        if not docs:
            return []

        cleaned_docs = [self._clean_knowledge_text(doc.get("content", "")) for doc in docs if doc.get("content")]
        if not cleaned_docs:
            return []

        focus_terms = [token for token in re.split(r"[^\w\u4e00-\u9fff]+", query.lower()) if len(token) >= 2]
        chosen: List[str] = []

        for content in cleaned_docs:
            sentences = [
                sentence.strip(" ;；")
                for sentence in re.split(r"(?<=[。！？.!?；;])\s+|(?<=[。！？.!?；;])", content)
                if sentence.strip()
            ]
            definition = next(
                (
                    sentence
                    for sentence in sentences
                    if any(term in sentence.lower() for term in focus_terms) and ("是" in sentence or "=" in sentence or "指" in sentence)
                ),
                None,
            )
            if definition:
                chosen.append(definition)
                break

        formula = None
        for content in cleaned_docs:
            formula = next(
                (
                    segment.strip(" ;；")
                    for segment in re.split(r"(?<=[。！？.!?；;])\s+|(?<=[。！？.!?；;])", content)
                    if "=" in segment or "计算" in segment or "公式" in segment
                ),
                None,
            )
            if formula:
                break

        if not chosen:
            chosen.append(cleaned_docs[0][:180].strip())
        if formula and formula not in chosen:
            chosen.append(formula[:180].strip())
        return chosen[:2]

    @staticmethod
    def _build_supporting_chunks(documents: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
        supporting_chunks: List[Dict[str, Any]] = []
        for doc in documents[:limit]:
            metadata = doc.get("metadata") or {}
            # Preserve newlines for markdown rendering in frontend
            snippet = (doc.get("raw_content") or doc.get("content") or "").strip()
            supporting_chunks.append(
                {
                    "title": doc.get("title") or doc.get("source"),
                    "section": doc.get("section"),
                    "source": doc.get("source"),
                    "snippet": snippet[:500],  # Increased limit slightly to allow for structure
                    "url": metadata.get("url"),
                    "score": doc.get("score"),
                    "chunk_type": metadata.get("chunk_type"),
                    "source_type": metadata.get("source_type"),
                    "date": metadata.get("date") or metadata.get("published"),
                    "asset_code": metadata.get("asset_code"),
                }
            )
        return supporting_chunks

    @staticmethod
    def _build_market_rows(tool_results: List[ToolResult]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for result in tool_results:
            data = result.data
            source = data.get("source", result.tool)
            timestamp = data.get("timestamp")

            if result.tool == "get_price" and data.get("price") is not None:
                rows.append({"metric": "latest_price", "value": data["price"], "unit": data.get("currency") or "", "timestamp": timestamp, "source": source})
            elif result.tool == "get_change" and data.get("change_pct") is not None:
                rows.append({"metric": "interval_change_pct", "value": data["change_pct"], "unit": "%", "timestamp": timestamp, "source": source})
                rows.append({"metric": "trend", "value": data.get("trend"), "unit": "", "timestamp": timestamp, "source": source})
            elif result.tool == "get_metrics":
                for metric, unit in (
                    ("annualized_volatility", "%"),
                    ("total_return_pct", "%"),
                    ("max_drawdown_pct", "%"),
                    ("annualized_return_pct", "%"),
                    ("sharpe_ratio", ""),
                ):
                    if data.get(metric) is not None:
                        rows.append({"metric": metric, "value": data[metric], "unit": unit, "timestamp": timestamp, "source": source})
            elif result.tool == "get_info":
                if data.get("name"):
                    rows.append({"metric": "asset_name", "value": data["name"], "unit": "", "timestamp": timestamp, "source": source})
                if data.get("pe_ratio") is not None:
                    rows.append({"metric": "pe_ratio", "value": data["pe_ratio"], "unit": "", "timestamp": timestamp, "source": source})
        return rows

    def _compose_structured_answer(
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
            warnings.append("本系统不提供投资建议。")
        if validation["level"] == "low":
            warnings.append("当前回答基于有限上下文，可能不完整。")

        comparison = by_tool.get("compare_assets")
        if comparison:
            rows = comparison.get("rows", [])
            blocks.append(
                StructuredBlock(
                    type="table",
                    title="标的对比",
                    data={"columns": ["symbol", "price", "total_return_pct", "annualized_volatility", "max_drawdown_pct"], "rows": rows},
                )
            )
            blocks.append(
                StructuredBlock(
                    type="chart",
                    title="对比图表",
                    data={"chart_type": "comparison", "range_key": comparison.get("range_key"), "series": comparison.get("chart", [])},
                )
            )
            lines = ["客观数据摘要:", "- 标的对比完成。"]
            if warnings:
                blocks.append(StructuredBlock(type="warning", title="风险提示", data={"items": warnings}))
                lines.extend(["", "分析及参考:", *[f"- {item}" for item in warnings]])
            return "\n".join(lines), blocks

        market_rows = self._build_market_rows(tool_results)
        price = by_tool.get("get_price")
        change = by_tool.get("get_change")
        history = by_tool.get("get_history")
        knowledge = by_tool.get("search_knowledge")
        sec_results = by_tool.get("search_sec")
        web_results = by_tool.get("search_web")

        objective_lines: List[str] = []
        analysis_lines: List[str] = []
        insight_items: List[str] = []

        if market_rows:
            blocks.append(
                StructuredBlock(
                    type="table",
                    title="客观数据",
                    data={"columns": ["metric", "value", "unit", "timestamp", "source"], "rows": market_rows},
                )
            )
        _CURRENCY_LABELS = {"USD": "美元", "CNY": "人民币", "HKD": "港币", "EUR": "欧元", "GBP": "英镑"}
        if price and price.get("price") is not None:
            currency = (price.get("currency") or "").upper()
            currency_display = _CURRENCY_LABELS.get(currency, currency) if currency else ""
            objective_lines.append(f"{price['symbol']} 最新价格：{price['price']:.2f} {currency_display}".strip())
        if change and change.get("change_pct") is not None:
            objective_lines.append(f"区间涨跌：{change['change_pct']:+.2f}%。")
            insight_items.append(f"涨跌幅：{change['change_pct']:+.2f}%")

        if history and history.get("data"):
            blocks.append(
                StructuredBlock(
                    type="chart",
                    title="价格走势",
                    data={"chart_type": "history", "symbol": history["symbol"], "range_key": history.get("range_key"), "series": history.get("data", [])},
                )
            )
            if technical_analysis and not technical_analysis.get("error"):
                trend = technical_analysis.get("trend")
                rsi = technical_analysis.get("rsi")
                if trend is not None:
                    insight_items.append(f"趋势：{trend}")
                if rsi is not None:
                    insight_items.append(f"RSI：{rsi}")
                if technical_analysis.get("max_drawdown_pct") is not None:
                    insight_items.append(f"最大回撤：{technical_analysis['max_drawdown_pct']:+.2f}%")
                if trend is not None or rsi is not None:
                    analysis_lines.append(f"技术指标参考：trend={trend}，RSI={rsi}。")

        if insight_items:
            blocks.insert(0, StructuredBlock(type="bullets", title="核心要点", data={"items": insight_items}))

        if knowledge and knowledge.get("documents"):
            docs = knowledge["documents"][:3]
            support = self._build_supporting_chunks(docs, limit=3)
            knowledge_summary = self._summarize_knowledge_documents(query, docs)
            blocks.append(
                StructuredBlock(
                    type="quote",
                    title="知识库摘要",
                    data={},
                    supporting_chunks=support,
                )
            )
            if degraded_mode:
                objective_lines.insert(0, self.DEGRADED_NOTE)
                objective_lines.extend(knowledge_summary or [item["snippet"] for item in support[:2] if item.get("snippet")])
            elif not objective_lines:
                objective_lines.extend(knowledge_summary)
            else:
                analysis_lines.append("知识库信息已整合分析。")

        if sec_results and sec_results.get("results"):
            sec_items = [f"{item.get('title')} ({item.get('published') or 'unknown'})" for item in sec_results["results"][:3]]
            blocks.append(StructuredBlock(type="bullets", title="SEC及财报公告", data={"items": sec_items}))
            analysis_lines.append("SEC财报公告数据已添加。")

        if web_results and web_results.get("results"):
            web_items = [item.get("title") for item in web_results["results"][:3] if item.get("title")]
            support = [
                {
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "snippet": item.get("snippet", "")[:220],
                    "url": item.get("url"),
                    "date": item.get("published"),
                    "source_type": "web",
                }
                for item in web_results["results"][:3]
            ]
            blocks.append(
                StructuredBlock(
                    type="bullets",
                    title="相关市场新闻",
                    data={"items": web_items},
                    supporting_chunks=support,
                )
            )
            analysis_lines.append("近期市场新闻动态已添加。")

        if warnings:
            analysis_lines.extend(warnings)
            blocks.append(StructuredBlock(type="warning", title="风险提示", data={"items": warnings}))

        summary_sections: List[str] = []
        if objective_lines:
            summary_sections.append("客观数据摘要:\n- " + "\n- ".join(dict.fromkeys(line for line in objective_lines if line)))
        if analysis_lines:
            summary_sections.append("分析及参考:\n- " + "\n- ".join(dict.fromkeys(line for line in analysis_lines if line)))

        if summary_sections:
            return "\n\n".join(summary_sections), blocks
        return f"上下文不足，无法可靠回答：{query}", blocks

    async def run(self, query: str, model_name: Optional[str] = None) -> AsyncGenerator[SSEEvent, None]:
        logger.info(f"[AgentCore.run] START - Query: {query}")
        request_id = str(uuid.uuid4())
        tool_results: List[ToolResult] = []
        degraded_mode = self.is_degraded_mode()
        selected_model = model_name or self._select_model(query)
        logger.info(f"[AgentCore.run] Model selected: {selected_model}, degraded_mode: {degraded_mode}")

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

        route = await self.query_router.classify_async(query)
        logger.info(f"[AgentCore.run] Route classified: type={route.query_type}, requires_knowledge={route.requires_knowledge}")
        should_force_rule_route = (
            route.query_type == QueryType.KNOWLEDGE
            and route.requires_knowledge
            and not route.symbols
        )
        logger.info(f"[AgentCore.run] should_force_rule_route: {should_force_rule_route}")

        if self.use_llm_routing and not degraded_mode and not should_force_rule_route:
            llm_route = await self.llm_router.route(query)
            tool_plan = llm_route.tools_to_call
            if tool_plan and not getattr(llm_route, "is_fallback", False):
                route = None
            else:
                tool_plan = None
        else:
            tool_plan = None

        if route and route.refuses_advice is True:
            refusal = "我不能提供买入/卖出/推荐/目标价等投资建议。"
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
                    "blocks": [StructuredBlock(type="warning", title="合规提示", data={"items": ["本系统不提供投资建议。"]}).model_dump()],
                    "route": {"type": route.query_type.value, "symbols": route.symbols},
                    "disclaimer": "以上内容仅供参考，不构成投资建议。",
                },
            )
            return

        try:
            if tool_plan is None:
                logger.info("[AgentCore.run] Building tool plan from route")
                tool_plan = await self._build_tool_plan(route)
                logger.info(f"[AgentCore.run] Tool plan built: {[step['name'] for step in tool_plan] if tool_plan else []}")

            stages = tool_plan if tool_plan and isinstance(tool_plan[0], list) else [tool_plan]
            logger.info(f"[AgentCore.run] Executing {len(stages)} stages")
            for stage_idx, stage in enumerate(stages):
                if not stage:
                    continue
                logger.info(f"[AgentCore.run] Stage {stage_idx}: {[step['name'] for step in stage]}")
                for step in stage:
                    yield SSEEvent(type="tool_start", name=step["name"], display=step["display"])

                raw_results = await self._execute_tools_parallel(stage, degraded_mode=degraded_mode)
                logger.info(f"[AgentCore.run] Stage {stage_idx} completed, {len(raw_results)} results")
                for raw_result in raw_results:
                    if not raw_result["success"]:
                        logger.warning(f"[AgentCore.run] Tool {raw_result['tool']} failed")
                        continue
                    tool_result = self._normalize_tool_result(raw_result)
                    tool_results.append(tool_result)
                    yield SSEEvent(type="tool_data", tool=raw_result["tool"], data=raw_result["data"])

            logger.info(f"[AgentCore.run] All tools executed, total results: {len(tool_results)}")
            validation = self.data_validator.validate_tool_results(tool_results)
            logger.info(f"[AgentCore.run] Validation result: {validation}")
            knowledge_payload = next(
                (result.data for result in tool_results if result.tool == "search_knowledge" and result.status == "success"),
                None,
            )
            if route and route.query_type == QueryType.KNOWLEDGE and knowledge_payload and knowledge_payload.get("documents"):
                retrieval_confidence = float(knowledge_payload.get("confidence", 0.0))
                if retrieval_confidence >= 0.75:
                    validation["confidence"] = max(validation["confidence"], 80)
                    validation["level"] = "high"
                elif retrieval_confidence >= 0.45:
                    validation["confidence"] = max(validation["confidence"], 60)
                    validation["level"] = "medium"
                else:
                    validation["confidence"] = max(validation["confidence"], 45)
                    validation["level"] = "medium"
            sources = self._build_sources(tool_results)

            symbols: List[str] = []
            if route:
                symbols = route.symbols
            else:
                for result in tool_results:
                    if result.tool in ["get_price", "get_history", "get_info", "get_metrics"]:
                        symbol = result.data.get("symbol")
                        if symbol and symbol not in symbols:
                            symbols.append(symbol)

            if self.data_validator.should_block_response(validation):
                fallback = self.data_validator.get_fallback_message(validation, symbols[0] if symbols else "current query")
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

            if route is None:
                route = QueryRoute(
                    query_type=QueryType.HYBRID,
                    cleaned_query=query,
                    symbols=symbols,
                    requires_knowledge=any(r.tool == "search_knowledge" for r in tool_results),
                    requires_web=any(r.tool == "search_web" for r in tool_results),
                )

            final_text, blocks = self._compose_structured_answer(
                query,
                route,
                tool_results,
                technical_analysis,
                validation,
                degraded_mode=degraded_mode,
            )
            # Send the structured blocks instantly for the frontend to render UI cards!
            yield SSEEvent(type="blocks", data=[block.model_dump() for block in blocks])
            
            # STAGE 3: Strict LLM Synthesis (Anti-Hallucination Guardrails)
            final_summary = ""
            if not degraded_mode and model_config:
                from app.models.model_adapter import ModelAdapterFactory
                adapter = ModelAdapterFactory.create_adapter(model_config)
                
                base_system_prompt = get_prompt("generator", "system_prompt") or ""
                hard_guardrails = """绝对禁令（Guardrails）：
1. 你的回答必须100%基于用户提供的上下文数据，不允许引入任何外部未提供的数值或事实。
2. 禁止预测未来走势、买卖推荐、目标价等投资建议。
3. 若数据不足，必须明确说明“缺乏足够数据支撑”，不要推测或估算。
4. 必须使用简体中文回答，并在末尾强调免责声明。
5. 禁止使用英文作为小节标题或术语。必须使用中文，例如：客观证据、分析、关键要点、涨跌幅、美元。禁止：Objective Evidence、Analysis、KEY POINTS、Change、USD。"""

                system_prompt = (base_system_prompt.strip() + "\n\n" + hard_guardrails).strip() if base_system_prompt else hard_guardrails

                user_template = get_prompt("generator", "user_template")
                api_completeness = max(0.0, min(1.0, float(validation.get("confidence", 0.0)) / 100.0))
                rag_relevance = 0.0
                rag_context = ""
                try:
                    knowledge_payload = next(
                        (result.data for result in tool_results if result.tool == "search_knowledge" and result.status == "success"),
                        None,
                    )
                    if knowledge_payload:
                        rag_relevance = max(0.0, min(1.0, float(knowledge_payload.get("confidence", 0.0) or 0.0)))
                        docs = knowledge_payload.get("documents") or []
                        rag_context = "\n\n".join((doc.get("content") or "") for doc in docs[:5]).strip()
                except Exception:
                    pass

                user_content = None
                if user_template:
                    try:
                        user_content = user_template.format(
                            user_question=query,
                            api_data=final_text,
                            rag_context=rag_context or "暂无",
                            api_completeness=f"{api_completeness:.2f}",
                            rag_relevance=f"{rag_relevance:.2f}",
                        )
                    except Exception:
                        user_content = None

                if not user_content:
                    user_content = f"【用户问题】\n{query}\n\n【客观上下文】\n{final_text}\n\n请严格基于上述客观上下文生成回答。"

                try:
                    summary_stream = adapter.create_message_stream(
                        messages=[{"role": "user", "content": user_content}],
                        system=system_prompt,
                        tools=None,
                        max_tokens=1500
                    )
                    async for chunk in summary_stream:
                        if chunk and chunk.get("type") == "content_block_delta":
                            text_part = chunk.get("delta", {}).get("text", "")
                            if text_part:
                                final_summary += text_part
                                yield SSEEvent(type="chunk", text=text_part)
                except Exception as e:
                    # Fallback if streaming fails
                    print(f"Synthesis failed: {e}")
                    final_summary = final_text
                    yield SSEEvent(type="chunk", text=final_text)
            else:
                final_summary = final_text
                yield SSEEvent(type="chunk", text=final_text)

            self.model_manager.record_usage(model_name=selected_model, tokens_input=len(query) // 4, tokens_output=len(final_summary) // 4, success=True)
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
            logger.error(f"[AgentCore.run] EXCEPTION caught: {exc}", exc_info=True)
            self.model_manager.record_usage(model_name=selected_model, tokens_input=len(query) // 4, tokens_output=0, success=False)
            yield SSEEvent(type="error", message=str(exc), code="LLM_ERROR", model=selected_model)

    def get_available_models(self) -> List[Dict[str, Any]]:
        return self.model_manager.list_models()

    def get_usage_report(self) -> Dict[str, Any]:
        return self.model_manager.get_usage_report()
