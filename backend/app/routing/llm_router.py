"""LLM-based query router using function calling for intelligent tool selection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.multi_model import model_manager
from app.models.model_adapter import ModelAdapterFactory


@dataclass
class LLMRoute:
    """LLM-generated routing decision."""

    tools_to_call: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    symbols: List[str] = field(default_factory=list)
    requires_chart: bool = False


class LLMQueryRouter:
    """Use LLM function calling to intelligently route queries to appropriate tools."""

    ROUTING_TOOLS = [
        {
            "name": "get_stock_price",
            "description": "获取股票的实时价格、涨跌幅等市场数据。适用于：查询当前价格、今日涨跌、实时行情。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码，如 AAPL, TSLA, BABA"
                    },
                    "include_history": {
                        "type": "boolean",
                        "description": "是否包含历史走势数据（用于生成图表）",
                        "default": False
                    },
                    "time_range": {
                        "type": "string",
                        "description": "时间范围：1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y",
                        "default": "1mo"
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "search_knowledge",
            "description": "搜索金融知识库，查询金融术语、概念、指标的定义和解释。适用于：什么是XX、XX的定义、如何计算XX、金融概念解释。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的金融术语或概念"
                    },
                    "category": {
                        "type": "string",
                        "description": "知识类别：估值指标、财务报表、技术分析、宏观经济、投资策略等",
                        "default": None
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_news",
            "description": "搜索最新的市场新闻和事件。适用于：为什么涨/跌、最近发生了什么、新闻事件、市场动态。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "新闻搜索关键词"
                    },
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "相关的股票代码（可选）",
                        "default": []
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "compare_stocks",
            "description": "对比多个股票的表现。适用于：对比、比较、哪个更好、XX vs YY。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的股票代码列表（2-4个）"
                    },
                    "time_range": {
                        "type": "string",
                        "description": "对比时间范围：1mo, 3mo, 6mo, 1y, 2y",
                        "default": "1y"
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "对比指标：price_change, volatility, return, max_drawdown",
                        "default": ["price_change", "return"]
                    }
                },
                "required": ["symbols"]
            }
        },
        {
            "name": "get_company_info",
            "description": "获取公司基本信息和财务数据。适用于：公司简介、市值、PE/PB比率、财务指标。",
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
        }
    ]

    SYSTEM_PROMPT = """你是一个金融查询路由助手。根据用户的问题，选择合适的工具来回答。

工具选择原则：
1. 股票价格/行情类问题 → get_stock_price
2. 金融术语/概念类问题 → search_knowledge
3. 新闻/事件/原因类问题 → search_news
4. 对比类问题 → compare_stocks
5. 公司信息类问题 → get_company_info

可以同时调用多个工具。例如：
- "特斯拉为什么大涨" → get_stock_price + search_news
- "什么是市盈率，苹果的市盈率是多少" → search_knowledge + get_company_info

重要：
- 识别中文公司名并转换为股票代码（苹果→AAPL, 特斯拉→TSLA, 阿里巴巴→BABA等）
- 如果问题涉及走势、图表、历史数据，设置 include_history=true
- 优先使用最相关的工具，避免过度调用"""

    CHINESE_COMPANY_MAP = {
        "苹果": "AAPL",
        "特斯拉": "TSLA",
        "阿里巴巴": "BABA",
        "阿里": "BABA",
        "腾讯": "0700.HK",
        "英伟达": "NVDA",
        "微软": "MSFT",
        "亚马逊": "AMZN",
        "谷歌": "GOOGL",
        "茅台": "600519.SS",
        "贵州茅台": "600519.SS",
        "比亚迪": "002594.SZ",
        "比特币": "BTC-USD",
        "以太坊": "ETH-USD",
    }

    def __init__(self):
        self.model_manager = model_manager

    async def route(self, query: str) -> LLMRoute:
        """Use LLM to determine which tools to call."""

        # Check if LLM is available
        if self.model_manager.is_degraded_mode():
            return self._fallback_route(query)

        try:
            # Build routing prompt
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题：{query}\n\n请选择合适的工具来回答这个问题。"}
            ]

            # Call LLM with function calling
            model_id = self.model_manager.select_model("medium")
            if not model_id:
                return self._fallback_route(query)

            model_config = self.model_manager.models.get(model_id)
            if not model_config:
                return self._fallback_route(query)

            adapter = ModelAdapterFactory.create_adapter(model_config)

            response = await adapter.chat(
                messages=messages,
                tools=self.ROUTING_TOOLS,
                temperature=0.1,  # Low temperature for consistent routing
                max_tokens=1000
            )

            # Parse tool calls from response
            tools_to_call = []
            symbols = []
            requires_chart = False

            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get('name', '')
                    tool_input = tool_call.get('input', {})

                    # Map routing tool names to actual tool names
                    actual_tool_name = self._map_tool_name(tool_name)
                    actual_params = self._map_tool_params(tool_name, tool_input)

                    tools_to_call.append({
                        "name": actual_tool_name,
                        "params": actual_params,
                        "display": self._get_tool_display(actual_tool_name, actual_params)
                    })

                    # Extract symbols
                    if 'symbol' in tool_input:
                        symbols.append(tool_input['symbol'])
                    if 'symbols' in tool_input:
                        symbols.extend(tool_input['symbols'])

                    # Check if chart is needed
                    if tool_input.get('include_history') or tool_name == 'compare_stocks':
                        requires_chart = True

            # Get reasoning from response text
            reasoning = response.get('content', '') if isinstance(response, dict) else str(response)

            return LLMRoute(
                tools_to_call=tools_to_call,
                reasoning=reasoning,
                symbols=list(set(symbols)),  # Deduplicate
                requires_chart=requires_chart
            )

        except Exception as e:
            print(f"LLM routing failed: {e}, falling back to rule-based routing")
            return self._fallback_route(query)

    def _map_tool_name(self, routing_tool_name: str) -> str:
        """Map routing tool names to actual backend tool names."""
        mapping = {
            "get_stock_price": "get_price",
            "search_knowledge": "search_knowledge",
            "search_news": "search_web",
            "compare_stocks": "compare_assets",
            "get_company_info": "get_info"
        }
        return mapping.get(routing_tool_name, routing_tool_name)

    def _map_tool_params(self, routing_tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Map routing tool parameters to actual backend parameters."""

        if routing_tool_name == "get_stock_price":
            params = {"symbol": tool_input.get("symbol")}
            if tool_input.get("include_history"):
                # Will trigger get_history call separately
                pass
            return params

        elif routing_tool_name == "compare_stocks":
            return {
                "symbols": tool_input.get("symbols", []),
                "range_key": tool_input.get("time_range", "1y")
            }

        elif routing_tool_name == "search_news":
            return {
                "query": tool_input.get("query"),
                "symbols": tool_input.get("symbols", [])
            }

        else:
            return tool_input

    def _get_tool_display(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Generate display text for tool execution."""

        if tool_name == "get_price":
            return f"正在获取 {params.get('symbol')} 的最新价格..."
        elif tool_name == "get_history":
            return f"正在获取 {params.get('symbol')} 的历史数据..."
        elif tool_name == "search_knowledge":
            return f"正在搜索知识库：{params.get('query')}"
        elif tool_name == "search_web":
            return f"正在搜索新闻：{params.get('query')}"
        elif tool_name == "compare_assets":
            symbols = params.get('symbols', [])
            return f"正在对比 {', '.join(symbols[:3])} 的表现..."
        elif tool_name == "get_info":
            return f"正在获取 {params.get('symbol')} 的公司信息..."
        else:
            return f"正在执行 {tool_name}..."

    def _fallback_route(self, query: str) -> LLMRoute:
        """Simple rule-based fallback when LLM is unavailable."""

        query_lower = query.lower()
        tools = []
        symbols = []

        # Extract symbols from Chinese company names
        for cn_name, symbol in self.CHINESE_COMPANY_MAP.items():
            if cn_name in query:
                symbols.append(symbol)

        # Simple keyword matching
        if any(kw in query for kw in ["价格", "股价", "多少钱", "行情", "price"]):
            if symbols:
                tools.append({
                    "name": "get_price",
                    "params": {"symbol": symbols[0]},
                    "display": f"正在获取 {symbols[0]} 的价格..."
                })

        if any(kw in query for kw in ["什么是", "定义", "如何", "怎么", "概念"]):
            tools.append({
                "name": "search_knowledge",
                "params": {"query": query},
                "display": f"正在搜索知识库..."
            })

        if any(kw in query for kw in ["为什么", "原因", "新闻", "消息", "事件"]):
            tools.append({
                "name": "search_web",
                "params": {"query": query},
                "display": f"正在搜索新闻..."
            })

        # Default to knowledge search if no tools matched
        if not tools:
            tools.append({
                "name": "search_knowledge",
                "params": {"query": query},
                "display": "正在搜索知识库..."
            })

        return LLMRoute(
            tools_to_call=tools,
            reasoning="使用规则路由（LLM不可用）",
            symbols=symbols,
            requires_chart=False
        )
