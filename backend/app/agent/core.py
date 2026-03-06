"""Agent core with deterministic routing and grounded response synthesis."""

import json
import re
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.market import MarketDataService
from app.models import SSEEvent, Source, ToolResult
from app.models.model_adapter import ModelAdapterFactory
from app.models.multi_model import model_manager
from app.rag.confidence import ConfidenceScorer
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.routing import QueryRouter, QueryType
from app.search import WebSearchService


class ResponseGuard:
    """Validates the final answer against tool output."""

    @staticmethod
    def validate(response_text: str, tool_results: List[ToolResult]) -> bool:
        if not response_text.strip():
            return False

        normalized_text = response_text.lower()

        grounded_numbers: set[str] = set()
        grounded_sources: set[str] = set()
        for result in tool_results:
            ResponseGuard._collect_numbers(result.data, grounded_numbers)
            source_name = result.data.get("source")
            if source_name:
                grounded_sources.add(str(source_name).lower())
            grounded_sources.add(result.data_source.lower())

        if not grounded_numbers:
            return True

        text_numbers = ResponseGuard._extract_numeric_tokens(response_text)
        allowed_numbers = grounded_numbers | ResponseGuard._allowable_numbers(tool_results)
        unsupported_numbers = {
            number
            for number in text_numbers
            if number not in allowed_numbers and not ResponseGuard._is_ignorable_number(number)
        }
        matched_number = any(number in text_numbers for number in grounded_numbers if number)
        has_source_section = "source" in normalized_text or "来源" in response_text
        matched_source = True
        if has_source_section and grounded_sources:
            matched_source = any(source in normalized_text for source in grounded_sources)
        return matched_number and matched_source and not unsupported_numbers

    @staticmethod
    def _collect_numbers(value: Any, bucket: set[str]):
        if isinstance(value, dict):
            for item in value.values():
                ResponseGuard._collect_numbers(item, bucket)
            return
        if isinstance(value, list):
            for item in value:
                ResponseGuard._collect_numbers(item, bucket)
            return
        if isinstance(value, (int, float)):
            bucket.add(f"{value}")
            bucket.add(f"{value:.2f}")
            bucket.add(f"{int(value)}")

    @staticmethod
    def _extract_numeric_tokens(text: str) -> set[str]:
        tokens = set()
        for raw_token in re.findall(r"\d+(?:\.\d+)?", text):
            normalized = raw_token.lstrip("0") or "0"
            tokens.add(normalized)
            if "." in normalized:
                try:
                    number = float(normalized)
                    tokens.add(f"{number:.2f}")
                    tokens.add(str(int(number)))
                except ValueError:
                    continue
            else:
                try:
                    number = int(normalized)
                    tokens.add(str(number))
                    tokens.add(f"{float(number):.2f}")
                except ValueError:
                    continue
        return tokens

    @staticmethod
    def _allowable_numbers(tool_results: List[ToolResult]) -> set[str]:
        allowed = set()
        for result in tool_results:
            payload = result.data
            if "timestamp" in payload and isinstance(payload["timestamp"], str):
                allowed.update(ResponseGuard._extract_numeric_tokens(payload["timestamp"]))
            if "published" in payload and isinstance(payload["published"], str):
                allowed.update(ResponseGuard._extract_numeric_tokens(payload["published"]))
        return allowed

    @staticmethod
    def _is_ignorable_number(token: str) -> bool:
        try:
            value = float(token)
            if not value.is_integer():
                return False
            return int(value) <= 5
        except ValueError:
            return False


class AgentCore:
    """
    Deterministic financial QA agent.

    The backend decides the workflow and tools. The LLM only explains verified
    results and never decides whether to fetch facts.
    """

    def __init__(self, preferred_model: Optional[str] = None):
        self.model_manager = model_manager
        self.preferred_model = preferred_model

        self.market_service = MarketDataService()
        self.rag_pipeline = HybridRAGPipeline()
        self.confidence_scorer = ConfidenceScorer()
        self.search_service = WebSearchService()
        self.query_router = QueryRouter()
        self.guard = ResponseGuard()
        self.tools = self._build_tools()

    def _build_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_price",
                "description": "Get the latest market price for an asset symbol.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Asset symbol such as AAPL or BABA"}
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "get_history",
                "description": "Get historical OHLCV price data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "days": {"type": "integer", "default": 30},
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "get_change",
                "description": "Calculate price change for a recent window.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "days": {"type": "integer", "default": 7},
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "get_info",
                "description": "Get company or asset profile information.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "search_knowledge",
                "description": "Search the internal financial knowledge base.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_web",
                "description": "Search external web and news sources.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        ]

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return a normalized result payload."""
        start_time = datetime.now()

        try:
            if tool_name == "get_price":
                result = await self.market_service.get_price(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "get_history":
                result = await self.market_service.get_history(tool_input["symbol"], tool_input.get("days", 30))
                data = result.model_dump()
            elif tool_name == "get_change":
                result = await self.market_service.get_change(tool_input["symbol"], tool_input.get("days", 7))
                data = result.model_dump()
            elif tool_name == "get_info":
                result = await self.market_service.get_info(tool_input["symbol"])
                data = result.model_dump()
            elif tool_name == "search_knowledge":
                result = await self.rag_pipeline.search(tool_input["query"], use_hybrid=True)
                confidence = 0.0
                if result.documents:
                    confidence = self.confidence_scorer.calculate(tool_input["query"], result.documents)
                data = result.model_dump()
                data["confidence"] = confidence
                data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)
            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
                data = result.model_dump()
            else:
                latency = int((datetime.now() - start_time).total_seconds() * 1000)
                return {
                    "success": True,
                    "tool": tool_name,
                    "data": {"error": f"Unknown tool: {tool_name}"},
                    "latency_ms": latency,
                    "status": "error",
                    "data_source": tool_name,
                    "cache_hit": False,
                    "error_message": f"Unknown tool: {tool_name}",
                }

            latency = int((datetime.now() - start_time).total_seconds() * 1000)
            data_source = data.get("source", tool_name) if isinstance(data, dict) else tool_name
            return {
                "success": True,
                "tool": tool_name,
                "data": data,
                "latency_ms": latency,
                "status": "success",
                "data_source": data_source,
                "cache_hit": False,
                "error_message": None,
            }
        except Exception as exc:
            latency = int((datetime.now() - start_time).total_seconds() * 1000)
            return {
                "success": False,
                "tool": tool_name,
                "data": {"error": str(exc)},
                "latency_ms": latency,
                "status": "error",
                "data_source": tool_name,
                "cache_hit": False,
                "error_message": str(exc),
                "error": str(exc),
            }

    def _select_model(self, query: str) -> str:
        if self.preferred_model:
            return self.preferred_model

        complexity = self.model_manager.classify_query(query)
        model_name = self.model_manager.select_model(complexity)
        print(f"[AgentCore] Query complexity: {complexity}, Selected model: {model_name}")
        return model_name

    def _build_tool_plan(self, query: str) -> List[Dict[str, Any]]:
        route = self.query_router.classify(query)
        primary_symbol = route.symbols[0] if route.symbols else None
        days = route.days or 30
        plan: List[Dict[str, Any]] = []

        def add_tool(name: str, params: Dict[str, Any], display: str):
            plan.append({"name": name, "params": params, "display": display})

        if route.query_type == QueryType.MARKET and primary_symbol:
            if route.requires_price:
                add_tool("get_price", {"symbol": primary_symbol}, f"Fetching latest price for {primary_symbol}...")
            if route.requires_change:
                add_tool("get_change", {"symbol": primary_symbol, "days": route.days or 7}, f"Calculating {route.days or 7} day change for {primary_symbol}...")
            if route.requires_history:
                add_tool("get_history", {"symbol": primary_symbol, "days": days}, f"Loading price history for {primary_symbol}...")
            if route.requires_info:
                add_tool("get_info", {"symbol": primary_symbol}, f"Loading profile for {primary_symbol}...")
        elif route.query_type == QueryType.KNOWLEDGE:
            if self._looks_like_generic_chat(route.cleaned_query):
                return []
            add_tool("search_knowledge", {"query": route.cleaned_query}, "Searching the financial knowledge base...")
        elif route.query_type == QueryType.NEWS:
            add_tool("search_web", {"query": route.cleaned_query}, "Searching recent market news...")
        elif route.query_type == QueryType.HYBRID:
            if primary_symbol:
                add_tool("get_change", {"symbol": primary_symbol, "days": route.days or 7}, f"Calculating price move for {primary_symbol}...")
                if route.requires_price:
                    add_tool("get_price", {"symbol": primary_symbol}, f"Fetching latest price for {primary_symbol}...")
                if route.requires_history:
                    add_tool("get_history", {"symbol": primary_symbol, "days": days}, f"Loading price history for {primary_symbol}...")
            if route.requires_knowledge:
                add_tool("search_knowledge", {"query": route.cleaned_query}, "Searching supporting background knowledge...")
            if route.requires_web or not primary_symbol:
                add_tool("search_web", {"query": route.cleaned_query}, "Searching recent market news...")

        return plan

    @staticmethod
    def _looks_like_generic_chat(query: str) -> bool:
        lowered = query.lower()
        generic_markers = {
            "\u6d4b\u8bd5",
            "\u4f60\u597d",
            "hello",
            "hi",
        }
        finance_markers = {
            "\u5e02\u76c8\u7387",
            "\u51c0\u5229\u6da6",
            "\u6536\u5165",
            "\u73b0\u91d1\u6d41",
            "\u80a1\u4ef7",
            "\u4ef7\u683c",
            "\u8d22\u62a5",
            "pe",
            "eps",
            "revenue",
            "profit",
            "market",
            "stock",
            "price",
        }
        if any(marker in lowered or marker in query for marker in generic_markers):
            return True
        return not any(marker in lowered or marker in query for marker in finance_markers)

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

    def _build_grounded_messages(self, query: str, tool_results: List[ToolResult]) -> List[Dict[str, str]]:
        tool_payload = [
            {
                "tool": result.tool,
                "data_source": result.data_source,
                "latency_ms": result.latency_ms,
                "data": result.data,
            }
            for result in tool_results
        ]
        content = (
            f"User question: {query}\n\n"
            "You must answer only from the verified tool results below.\n"
            "Do not invent prices, percentages, dates, or news events.\n"
            "Output exactly these four sections:\n"
            "1. Data Summary\n"
            "2. Analysis\n"
            "3. Sources\n"
            "4. Uncertainty\n"
            "If evidence is insufficient, explicitly say so.\n\n"
            f"Tool results JSON:\n{json.dumps(tool_payload, ensure_ascii=False, indent=2)}"
        )
        return [{"role": "user", "content": content}]

    def _fallback_response(self, tool_results: List[ToolResult]) -> str:
        lines = ["## Data Summary"]
        for result in tool_results:
            payload = result.data
            if result.tool == "get_price":
                lines.append(f"- {payload.get('symbol')}: {payload.get('price')} {payload.get('currency', '')}".strip())
            elif result.tool == "get_change":
                lines.append(f"- {payload.get('symbol')} {payload.get('days')} day change: {payload.get('change_pct')}%")
            elif result.tool == "get_info":
                lines.append(f"- {payload.get('symbol')} sector: {payload.get('sector') or 'unknown'}")
            elif result.tool == "search_knowledge":
                docs = payload.get("documents", [])
                if docs:
                    lines.append(f"- Knowledge: {docs[0].get('content', '')[:120]}")
            elif result.tool == "search_web":
                results = payload.get("results", [])
                if results:
                    lines.append(f"- News: {results[0].get('title', '')}")

        lines.extend(
            [
                "",
                "## Analysis",
                "- This answer is generated only from verified tool outputs.",
                "",
                "## Sources",
            ]
        )
        for result in tool_results:
            lines.append(f"- {result.data_source}")
        lines.extend(
            [
                "",
                "## Uncertainty",
                "- If you need a stronger conclusion, confirm that both market data and news providers are available.",
            ]
        )
        return "\n".join(lines)

    async def _stream_grounded_answer(
        self,
        query: str,
        model_name: str,
        tool_results: List[ToolResult],
    ) -> AsyncGenerator[SSEEvent, None]:
        model_config = self.model_manager.models[model_name]
        adapter = ModelAdapterFactory.create_adapter(model_config)
        messages = self._build_grounded_messages(query, tool_results) if tool_results else [{"role": "user", "content": query}]
        system_prompt = (
            "You are a financial QA assistant. "
            "If tool results are provided, stay grounded in them. "
            "If no tool results are provided, answer conservatively and do not invent financial facts."
        )

        final_text = ""
        try:
            stream = adapter.create_message_stream(
                messages=messages,
                system=system_prompt,
                tools=[],
                max_tokens=1200,
            )

            async for event in stream:
                if isinstance(event, dict) and "final_message" in event:
                    final_message = event["final_message"]
                    if hasattr(final_message, "content"):
                        for block in final_message.content:
                            if getattr(block, "type", None) == "text" and block.text and block.text not in final_text:
                                final_text += block.text
                    continue

                event_type = getattr(event, "type", None)
                if event_type == "content_block_delta" and getattr(event, "delta", None):
                    if getattr(event.delta, "type", None) == "text_delta":
                        final_text += event.delta.text
                        yield SSEEvent(type="chunk", text=event.delta.text)
                elif isinstance(event, dict) and event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        final_text += text
                        yield SSEEvent(type="chunk", text=text)
        except Exception:
            if not tool_results:
                raise
            final_text = ""

        if not final_text and tool_results:
            yield SSEEvent(type="chunk", text=self._fallback_response(tool_results))

    async def run(self, query: str, model_name: Optional[str] = None) -> AsyncGenerator[SSEEvent, None]:
        """Run the grounded workflow with streaming response."""
        request_id = str(uuid.uuid4())
        tool_results: List[ToolResult] = []
        sources: List[Source] = []

        if not model_name:
            model_name = self._select_model(query)

        model_config = self.model_manager.models.get(model_name)
        if not model_config:
            yield SSEEvent(
                type="error",
                message=f"Model {model_name} not found",
                code="MODEL_NOT_FOUND",
            )
            return

        yield SSEEvent(
            type="model_selected",
            model=model_name,
            provider=model_config.provider,
            complexity=self.model_manager.classify_query(query),
        )

        tokens_input = len(query) // 4
        tokens_output = 0

        try:
            tool_plan = self._build_tool_plan(query)
            for step in tool_plan:
                yield SSEEvent(type="tool_start", name=step["name"], display=step["display"])
                raw_result = await self._execute_tool(step["name"], step["params"])
                if not raw_result["success"]:
                    raise RuntimeError(raw_result["error"])

                tool_result = self._normalize_tool_result(raw_result)
                tool_results.append(tool_result)

                payload = tool_result.data
                timestamp = payload.get("timestamp") or datetime.utcnow().isoformat()
                sources.append(Source(name=payload.get("source", step["name"]), timestamp=timestamp))
                yield SSEEvent(type="tool_data", tool=step["name"], data=payload)

            answer_chunks: List[str] = []
            async for answer_event in self._stream_grounded_answer(query, model_name, tool_results):
                if answer_event.text:
                    answer_chunks.append(answer_event.text)
                    tokens_output += len(answer_event.text) // 4
                yield answer_event

            final_text = "".join(answer_chunks)
            self.model_manager.record_usage(
                model_name=model_name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                success=True,
            )

            yield SSEEvent(
                type="done",
                verified=self.guard.validate(final_text, tool_results),
                sources=sources,
                request_id=request_id,
                model=model_name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
            )
        except Exception as exc:
            self.model_manager.record_usage(
                model_name=model_name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                success=False,
            )
            yield SSEEvent(
                type="error",
                message=str(exc),
                code="LLM_ERROR",
                model=model_name,
            )

    def get_available_models(self) -> List[Dict[str, Any]]:
        return self.model_manager.list_models()

    def get_usage_report(self) -> Dict[str, Any]:
        return self.model_manager.get_usage_report()
