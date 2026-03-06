"""
Agent Core - Multi-Model Tool Use with streaming
"""
import anthropic
import json
import uuid
from typing import AsyncGenerator, Dict, Any, List, Optional
from datetime import datetime
from app.config import settings
from app.models import SSEEvent, Source, ToolResult
from app.models.multi_model import model_manager, QueryComplexity, ModelProvider
from app.models.model_adapter import ModelAdapterFactory
from app.market import MarketDataService
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.rag.confidence import ConfidenceScorer
from app.search import WebSearchService


class ResponseGuard:
    """Validates LLM output against tool results"""

    @staticmethod
    def validate(response_text: str, tool_results: List[ToolResult]) -> bool:
        """
        Check if numbers in response match tool results

        Args:
            response_text: LLM generated response text
            tool_results: List of tool execution results

        Returns:
            bool: True if validation passes, False if hallucination detected
        """
        import re

        if not tool_results:
            return True

        # Extract numbers from response (prices, percentages, etc.)
        response_numbers = []
        for match in re.finditer(r'\d+\.?\d*', response_text):
            num = float(match.group())
            if num > 0.01:  # Ignore very small numbers
                response_numbers.append(num)

        # Extract key numbers from tool results
        tool_numbers = []
        for result in tool_results:
            if not hasattr(result, 'data') or not result.data:
                continue

            data = result.data

            # Price
            if 'price' in data and data['price']:
                tool_numbers.append(float(data['price']))

            # Change percentage (absolute value)
            if 'change_pct' in data and data['change_pct'] is not None:
                tool_numbers.append(abs(float(data['change_pct'])))

            # Market cap (convert to billions)
            if 'market_cap' in data and data['market_cap']:
                tool_numbers.append(float(data['market_cap']) / 1e9)

            # PE ratio
            if 'pe_ratio' in data and data['pe_ratio']:
                tool_numbers.append(float(data['pe_ratio']))

        if not tool_numbers:
            return True

        # Check if response numbers match tool results (within 5% tolerance)
        for rn in response_numbers:
            matched = False
            for tn in tool_numbers:
                if tn == 0:
                    continue
                error_rate = abs(rn - tn) / tn
                if error_rate < 0.05:  # 5% tolerance
                    matched = True
                    break

            # If large number doesn't match, validation fails
            if not matched and rn > 10:
                print(f"[ResponseGuard] Validation failed: {rn} doesn't match tool results")
                return False

        return True


class AgentCore:
    """
    Multi-Model Agent with Tool Use
    Supports Claude, DeepSeek, GPT, and other models
    Handles streaming responses and tool execution
    """

    def __init__(self, preferred_model: Optional[str] = None):
        # Multi-model manager
        self.model_manager = model_manager
        self.preferred_model = preferred_model

        # Services
        self.market_service = MarketDataService()
        self.rag_pipeline = HybridRAGPipeline()
        self.confidence_scorer = ConfidenceScorer()
        self.search_service = WebSearchService()
        self.guard = ResponseGuard()

        # Current adapter (will be set per request)
        self.current_adapter = None
        self.current_model_name = None

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
                result = await self.rag_pipeline.search(tool_input["query"], use_hybrid=True)

                # 计算置信度
                confidence = 0.0
                if result.documents:
                    confidence = self.confidence_scorer.calculate(
                        tool_input["query"],
                        result.documents
                    )

                data = result.model_dump()
                data["confidence"] = confidence
                data["confidence_level"] = self.confidence_scorer.get_confidence_level(confidence)

            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
                data = result.model_dump()

            else:
                data = {"error": f"Unknown tool: {tool_name}"}

            latency = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "success": True,
                "data": data,
                "latency_ms": latency,
                "tool": tool_name
            }

        except Exception as e:
            latency = int((datetime.now() - start_time).total_seconds() * 1000)
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency,
                "tool": tool_name
            }

    async def _execute_tools_parallel(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tools in parallel

        Args:
            tool_calls: List of tool calls, format: [{"name": "get_price", "input": {...}}, ...]

        Returns:
            List of tool execution results
        """
        import asyncio

        if not tool_calls:
            return []

        # Create parallel tasks
        tasks = [
            self._execute_tool(call['name'], call['input'])
            for call in tool_calls
        ]

        # Execute in parallel, catch exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process exception results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'error': str(result),
                    'tool': tool_calls[i]['name'],
                    'latency_ms': 0
                })
            else:
                processed_results.append(result)

        return processed_results

    def _select_model(self, query: str) -> str:
        """选择合适的模型"""
        if self.preferred_model:
            return self.preferred_model

        # 自动分类查询复杂度
        complexity = self.model_manager.classify_query(query)
        model_name = self.model_manager.select_model(complexity)

        print(f"[AgentCore] Query complexity: {complexity}, Selected model: {model_name}")
        return model_name

    async def run(self, query: str, model_name: Optional[str] = None) -> AsyncGenerator[SSEEvent, None]:
        """
        Run agent with streaming response
        Yields SSE events: tool_start, tool_data, chunk, done, error

        Args:
            query: 用户查询
            model_name: 指定模型名称（可选，不指定则自动选择）
        """
        request_id = str(uuid.uuid4())
        tool_results = []
        sources = []

        # 选择模型
        if not model_name:
            model_name = self._select_model(query)

        self.current_model_name = model_name
        model_config = self.model_manager.models.get(model_name)

        if not model_config:
            yield SSEEvent(
                type="error",
                message=f"Model {model_name} not found",
                code="MODEL_NOT_FOUND"
            )
            return

        # 创建适配器
        self.current_adapter = ModelAdapterFactory.create_adapter(model_config)

        # 发送模型选择事件
        yield SSEEvent(
            type="model_selected",
            model=model_name,
            provider=model_config.provider,
            complexity=self.model_manager.classify_query(query)
        )

        # System prompt
        system_prompt = """你是专业的金融分析助手，为专业投资者提供决策参考。

【核心原则】
1. 所有金融数字必须来自工具调用，不要编造数据
2. 使用工具获取事实数据后，再组织回答
3. 回答必须结构化，按以下格式组织
4. 明确标注数据来源

【回答结构】（必须遵循）

📊 数据摘要
- 当前价格：[从 get_price 工具获取]
- 涨跌幅：[从 get_change 工具获取]
- 成交量：[如有数据则展示]

📈 技术分析
- RSI 指标：[从历史数据计算并解读：超买/超卖/正常]
- MACD 指标：[从历史数据计算并解读：金叉/死叉/震荡]
- 趋势判断：[上涨/下跌/震荡]

💡 参考观点
- 基于以上数据的客观分析
- 可能的交易机会或风险点
- 【重要】明确说明"以上内容仅供参考，不构成投资建议"

⚠️ 风险提示
- 技术风险：[如 RSI 超买则提示回调风险]
- 市场风险：[大盘走势、行业风险等]
- 其他风险：[政策、估值等]

【可用工具】
- get_price: 查询当前价格
- get_history: 查询历史数据（用于计算技术指标，建议获取 30 天数据）
- get_change: 计算涨跌幅
- get_info: 查询公司信息
- search_knowledge: 检索金融知识
- search_web: 搜索新闻事件

【重要提示】
- 必须先调用工具获取数据，再组织回答
- 技术指标需要历史数据，记得调用 get_history
- 回答要专业但易懂，避免过度使用术语
- 永远不要直接推荐"买入"或"卖出"，只提供"参考观点"
- 所有建议都要加上免责声明"""

        messages = [{"role": "user", "content": query}]

        # 记录token使用（初始估算）
        tokens_input = len(query) // 4  # 粗略估算
        tokens_output = 0

        try:
            # 使用适配器创建流式响应
            stream = self.current_adapter.create_message_stream(
                messages=messages,
                system=system_prompt,
                tools=self.tools,
                max_tokens=2048
            )

            async for event in stream:
                # 处理最终消息（包含完整信息）
                if isinstance(event, dict) and "final_message" in event:
                    final_message = event["final_message"]

                    # 处理工具调用
                    if hasattr(final_message, "content"):
                        for block in final_message.content:
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

                    # 获取最终文本
                    final_text = ""
                    if hasattr(final_message, "content"):
                        for block in final_message.content:
                            if block.type == "text":
                                final_text += block.text

                    tokens_output = len(final_text) // 4
                    continue

                # Tool use event
                if hasattr(event, "type") and event.type == "content_block_start":
                    if hasattr(event, "content_block") and event.content_block.type == "tool_use":
                        tool_name = event.content_block.name
                        yield SSEEvent(
                            type="tool_start",
                            name=tool_name,
                            display=f"正在调用 {tool_name}..."
                        )

                # Text delta
                elif hasattr(event, "type") and event.type == "content_block_delta":
                    if hasattr(event, "delta") and event.delta.type == "text_delta":
                        tokens_output += len(event.delta.text) // 4
                        yield SSEEvent(
                            type="chunk",
                            text=event.delta.text
                        )

            # 记录使用情况
            self.model_manager.record_usage(
                model_name=model_name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                success=True
            )

            # Validate response
            verified = self.guard.validate(final_text if 'final_text' in locals() else "", tool_results)

            # Send done event
            yield SSEEvent(
                type="done",
                verified=verified,
                sources=sources,
                request_id=request_id,
                model=model_name,
                tokens_input=tokens_input,
                tokens_output=tokens_output
            )

        except Exception as e:
            # 记录失败
            self.model_manager.record_usage(
                model_name=model_name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                success=False
            )

            yield SSEEvent(
                type="error",
                message=str(e),
                code="LLM_ERROR",
                model=model_name
            )

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        return self.model_manager.list_models()

    def get_usage_report(self) -> Dict[str, Any]:
        """获取使用报告"""
        return self.model_manager.get_usage_report()
