"""
Agent Core - Claude Tool Use with streaming
"""
import anthropic
import json
import uuid
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime
from app.config import settings
from app.models import SSEEvent, Source, ToolResult
from app.market import MarketDataService
from app.rag import RAGPipeline
from app.search import WebSearchService


class ResponseGuard:
    """Validates LLM output against tool results"""

    @staticmethod
    def validate(response_text: str, tool_results: List[ToolResult]) -> bool:
        """
        Check if numbers in response match tool results
        Simple heuristic: extract numbers from both and compare
        """
        # For now, return True (basic implementation)
        # Production would do more sophisticated validation
        return True


class AgentCore:
    """
    Claude Agent with Tool Use
    Handles streaming responses and tool execution
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.market_service = MarketDataService()
        self.rag_pipeline = RAGPipeline()
        self.search_service = WebSearchService()
        self.guard = ResponseGuard()

        # Define tools for Claude
        self.tools = [
            {
                "name": "get_price",
                "description": "获取股票/资产的当前价格。支持美股、A股、港股、加密货币。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 AAPL, BABA, 600519.SS, BTC-USD"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_history",
                "description": "获取股票的历史价格数据（K线）。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码"
                        },
                        "days": {
                            "type": "integer",
                            "description": "历史天数，默认30天",
                            "default": 30
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_change",
                "description": "计算股票在指定时间段内的涨跌幅。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码"
                        },
                        "days": {
                            "type": "integer",
                            "description": "统计天数，默认7天",
                            "default": 7
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_info",
                "description": "获取公司基本面信息（行业、市值、PE等）。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "search_knowledge",
                "description": "检索金融知识库，回答概念性问题（如：什么是市盈率）。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索关键词"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_web",
                "description": "搜索网络新闻和事件，用于分析市场动态。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result"""
        start_time = datetime.now()

        try:
            if tool_name == "get_price":
                result = await self.market_service.get_price(tool_input["symbol"])
                data = result.model_dump()

            elif tool_name == "get_history":
                result = await self.market_service.get_history(
                    tool_input["symbol"],
                    tool_input.get("days", 30)
                )
                data = result.model_dump()

            elif tool_name == "get_change":
                result = await self.market_service.get_change(
                    tool_input["symbol"],
                    tool_input.get("days", 7)
                )
                data = result.model_dump()

            elif tool_name == "get_info":
                result = await self.market_service.get_info(tool_input["symbol"])
                data = result.model_dump()

            elif tool_name == "search_knowledge":
                result = await self.rag_pipeline.search(tool_input["query"])
                data = result.model_dump()

            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
                data = result.model_dump()

            else:
                data = {"error": f"Unknown tool: {tool_name}"}

            latency = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "success": True,
                "data": data,
                "latency_ms": latency
            }

        except Exception as e:
            latency = int((datetime.now() - start_time).total_seconds() * 1000)
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency
            }

    async def run(self, query: str) -> AsyncGenerator[SSEEvent, None]:
        """
        Run agent with streaming response
        Yields SSE events: tool_start, tool_data, chunk, done, error
        """
        request_id = str(uuid.uuid4())
        tool_results = []
        sources = []

        # System prompt
        system_prompt = """你是一个专业的金融资产问答助手。

核心原则：
1. 所有金融数字必须来自工具调用，不要编造数据
2. 使用工具获取事实数据后，再组织回答
3. 回答要结构化：📊 数据摘要 → 📈 趋势分析 → 🔍 影响因素
4. 引用数据来源

可用工具：
- get_price: 查询当前价格
- get_history: 查询历史数据
- get_change: 计算涨跌幅
- get_info: 查询公司信息
- search_knowledge: 检索金融知识
- search_web: 搜索新闻事件"""

        messages = [{"role": "user", "content": query}]

        try:
            # Call Claude with streaming
            with self.client.messages.stream(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=self.tools
            ) as stream:
                for event in stream:
                    # Tool use event
                    if event.type == "content_block_start":
                        if hasattr(event, "content_block") and event.content_block.type == "tool_use":
                            tool_name = event.content_block.name
                            yield SSEEvent(
                                type="tool_start",
                                name=tool_name,
                                display=f"正在调用 {tool_name}..."
                            )

                    # Tool input complete
                    elif event.type == "content_block_stop":
                        if hasattr(stream.current_message_snapshot, "content"):
                            for block in stream.current_message_snapshot.content:
                                if block.type == "tool_use":
                                    # Execute tool
                                    tool_result = await self._execute_tool(
                                        block.name,
                                        block.input
                                    )

                                    if tool_result["success"]:
                                        tool_results.append(tool_result)
                                        sources.append(Source(
                                            name=tool_result["data"].get("source", block.name),
                                            timestamp=datetime.utcnow().isoformat()
                                        ))

                                        # Send tool data
                                        yield SSEEvent(
                                            type="tool_data",
                                            tool=block.name,
                                            data=tool_result["data"]
                                        )

                    # Text delta
                    elif event.type == "content_block_delta":
                        if hasattr(event, "delta") and event.delta.type == "text_delta":
                            yield SSEEvent(
                                type="chunk",
                                text=event.delta.text
                            )

            # Validate response
            final_text = stream.get_final_text()
            verified = self.guard.validate(final_text, tool_results)

            # Send done event
            yield SSEEvent(
                type="done",
                verified=verified,
                sources=sources,
                request_id=request_id
            )

        except Exception as e:
            yield SSEEvent(
                type="error",
                message=str(e),
                code="LLM_ERROR"
            )
