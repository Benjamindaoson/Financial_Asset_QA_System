"""LLM-based query router using function calling for intelligent tool selection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import settings, get_prompt
from app.models.multi_model import model_manager
from app.models.model_adapter import ModelAdapterFactory


@dataclass
class LLMRoute:
    """LLM-generated routing decision."""

    tools_to_call: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    symbols: List[str] = field(default_factory=list)
    requires_chart: bool = False
    is_fallback: bool = False


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
            "name": "search_financial_dictionary",
            "description": "搜索金融知识库，查询金融术语、概念、指标的定义和解释。适用于：什么是市盈率、收入和净利润的区别是什么、如何计算XX、金融概念解释。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的金融术语或概念，例如 '市盈率', '收入与净利润的区别'"
                    },
                    "category": {
                        "type": "string",
                        "description": "知识类别：估值指标、财务报表、技术分析、宏观经济等",
                        "default": None
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_recent_earnings",
            "description": "获取某公司最近季度的财报数据和摘要。适用于：阿里巴巴最新财报摘要、特斯拉Q3业绩如何、苹果上季度营收利润。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码，如 AAPL, BABA"
                    },
                    "quarter": {
                        "type": "string",
                        "description": "指定季度（可选），例如 'Q3', '2023-Q4'",
                        "default": None
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "search_web_market_news",
            "description": "搜索外网最新的市场新闻和事件动态。适用于：为什么涨/跌、最近发生了什么重大事件、市场近期动态。",
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

    SYSTEM_PROMPT = """你是一个专业的金融查询智能路由引擎。根据用户的问题意图，选择合适的金融技能卡片（Skill）来回答。

    技能选择原则（必须严格遵守）：
    1. 客观行情查询：涉及股票当前价格、涨跌幅、实时走势 → `get_stock_price`
    2. 金融知识与概念解释：询问“什么是XX”、“XX和YY的区别”、“如何计算”、“指标含义” → `search_financial_dictionary` (必须利用内部知识库保证0幻觉)
    3. 财报数据提取：询问“某公司最近季度财报摘要”、“营收利润” → `search_recent_earnings` (必须从财报数据库调取)
    4. 市场新闻与动态因果：询问“为什么涨跌”、“最新消息”、“近期事件” → `search_web_market_news` (从外网检索最新动态)
    5. 标的对比：询问“对比A和B”、“表现如何” → `compare_stocks`
    6. 公司基础信息：询问“公司全称”、“属于什么行业”、“主营业务” → `get_company_info`

    执行逻辑：
    可以组合调用多个技能进行深度综合分析。例如：
    - "特斯拉为什么今天大涨" → 先调用 `get_stock_price` 取价格，再调用 `search_web_market_news` 取事件。
    - "什么是市盈率，阿里巴巴当前的市盈率是多少，最近财报如何" → 调用组合 `search_financial_dictionary` + `get_company_info` + `search_recent_earnings`。

    重要规则：
    - 提取实体时务必将中文名称规范化为股票代码（如 苹果→AAPL, 阿里巴巴→BABA 等）。
    - 绝不能自行捏造财务数字或金融定义，必须交由对应的工具处理。"""


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
            sys_prompt = get_prompt("router", "system_prompt") or self.SYSTEM_PROMPT
            user_tpl = get_prompt("router", "user_template")
            if user_tpl:
                try:
                    user_content = user_tpl.format(user_question=query)
                except Exception:
                    user_content = f"用户问题：{query}\n\n请选择合适的工具来回答这个问题。"
            else:
                user_content = f"用户问题：{query}\n\n请选择合适的工具来回答这个问题。"

            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_content},
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

            if not tools_to_call:
                return self._fallback_route(query)

            return LLMRoute(
                tools_to_call=tools_to_call,
                reasoning=reasoning,
                symbols=list(set(symbols)),  # Deduplicate
                requires_chart=requires_chart,
                is_fallback=False
            )

        except Exception as e:
            print(f"LLM routing failed: {e}, falling back to rule-based routing")
            return self._fallback_route(query)

    def _map_tool_name(self, routing_tool_name: str) -> str:
        """Map routing tool names to actual backend tool names."""
        mapping = {
            "get_stock_price": "get_price",
            "search_financial_dictionary": "search_knowledge",
            "search_web_market_news": "search_web",
            "search_recent_earnings": "search_sec",  # 财报直接映射到 SEC (或支持该功能的统一入口)
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

        elif routing_tool_name == "search_web_market_news":
            return {
                "query": tool_input.get("query"),
                "symbols": tool_input.get("symbols", [])
            }

        elif routing_tool_name == "search_recent_earnings":
            return {
                "symbol": tool_input.get("symbol"),
                "quarter": tool_input.get("quarter")
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
            return f"正在金融百科检索：{params.get('query')}"
        elif tool_name == "search_web":
            return f"正在全网聚合搜索动态：{params.get('query')}"
        elif tool_name == "search_sec":
            return f"正在底层财报库提取 {params.get('symbol', '')} 摘要..."

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

        if any(kw in query for kw in ["什么是", "定义", "如何", "怎么", "概念", "区别"]):
            tools.append({
                "name": "search_knowledge",
                "params": {"query": query},
                "display": f"正在金融百科检索..."
            })

        if any(kw in query for kw in ["为什么", "原因", "新闻", "消息", "事件", "动态"]):
            tools.append({
                "name": "search_web",
                "params": {"query": query},
                "display": f"正在全网聚合搜索动态..."
            })
            
        if any(kw in query for kw in ["财报", "业绩", "营收", "利润", "季报", "年报"]):
            if symbols:
                tools.append({
                    "name": "search_sec",
                    "params": {"symbol": symbols[0]},
                    "display": f"正在底层财报库提取摘要..."
                })

        # Default to knowledge search if no tools matched
        if not tools:
            tools.append({
                "name": "search_knowledge",
                "params": {"query": query},
                "display": "正在金融百科检索..."
            })


        return LLMRoute(
            tools_to_call=tools,
            reasoning="使用规则路由（LLM不可用）",
            symbols=symbols,
            requires_chart=False,
            is_fallback=True
        )
