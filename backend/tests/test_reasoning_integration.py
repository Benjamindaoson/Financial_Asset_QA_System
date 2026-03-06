"""
测试 Reasoning Layer 集成
"""
import pytest
from app.reasoning.query_router import QueryRouter
from app.reasoning.data_integrator import DataIntegrator
from app.reasoning.fast_analyzer import FastAnalyzer
from app.reasoning.decision_engine import DecisionEngine
from app.reasoning.response_generator import ResponseGenerator


class TestReasoningIntegration:
    """测试推理层集成"""

    @pytest.fixture
    def components(self):
        """创建所有组件"""
        return {
            "router": QueryRouter(),
            "integrator": DataIntegrator(),
            "analyzer": FastAnalyzer(),
            "decision": DecisionEngine(),
            "generator": ResponseGenerator()
        }

    def test_full_pipeline_price_query(self, components):
        """测试完整流程 - 价格查询"""
        # 1. 路由查询
        query_context = components["router"].route("苹果股票多少钱")
        
        assert query_context["mode"] == "fast"
        assert "AAPL" in query_context["symbols"]

        # 2. 模拟工具结果
        tool_results = [
            {
                "success": True,
                "tool": "get_price",
                "data": {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "price": 150.0,
                    "currency": "USD",
                    "source": "yfinance"
                }
            }
        ]

        # 3. 整合数据
        integrated = components["integrator"].integrate(tool_results, query_context)
        
        assert "AAPL" in integrated["symbols"]
        assert integrated["symbols"]["AAPL"]["price"]["current"] == 150.0

        # 4. 快速分析
        analysis = components["analyzer"].analyze(integrated, query_context)
        
        assert analysis["success"] is True
        assert analysis["type"] == "price"

        # 5. 生成决策（价格查询可能不需要决策）
        decision = components["decision"].generate_decision(analysis, integrated)
        
        assert decision["success"] is True

        # 6. 生成响应
        response = components["generator"].generate(analysis, decision, integrated)
        
        assert response["success"] is True
        assert "data_summary" in response["sections"]

    def test_full_pipeline_technical_query(self, components):
        """测试完整流程 - 技术分析查询"""
        # 1. 路由查询
        query_context = components["router"].route("特斯拉的技术分析")
        
        assert query_context["query_type"] == "technical"

        # 2. 模拟工具结果（包含历史数据）
        tool_results = [
            {
                "success": True,
                "tool": "get_price",
                "data": {
                    "symbol": "TSLA",
                    "name": "Tesla Inc.",
                    "price": 200.0,
                    "currency": "USD",
                    "source": "yfinance"
                }
            },
            {
                "success": True,
                "tool": "get_history",
                "data": {
                    "symbol": "TSLA",
                    "days": 30,
                    "data": [
                        {"date": f"2024-03-{i:02d}", "close": 190.0 + i * 0.5}
                        for i in range(1, 31)
                    ],
                    "source": "yfinance"
                }
            }
        ]

        # 3. 整合数据
        integrated = components["integrator"].integrate(tool_results, query_context)
        
        # 4. 计算技术指标
        symbol_data = integrated["symbols"]["TSLA"]
        technical = components["integrator"].calculate_technical_indicators(symbol_data)
        
        assert technical is not None
        assert "rsi" in technical
        assert "macd" in technical

        # 添加技术指标到数据中
        symbol_data["technical"] = technical

        # 5. 快速分析
        analysis = components["analyzer"].analyze(integrated, query_context)
        
        assert analysis["success"] is True

        # 6. 生成决策
        decision = components["decision"].generate_decision(analysis, integrated)
        
        assert decision["success"] is True
        assert "reference_view" in decision

        # 7. 生成响应
        response = components["generator"].generate(analysis, decision, integrated)
        
        assert response["success"] is True
        assert "technical_analysis" in response["sections"]

    def test_data_integrator_quality(self, components):
        """测试数据整合器的数据质量计算"""
        tool_results = [
            {
                "success": True,
                "tool": "get_price",
                "data": {
                    "symbol": "AAPL",
                    "price": 150.0,
                    "source": "yfinance"
                }
            },
            {
                "success": True,
                "tool": "get_change",
                "data": {
                    "symbol": "AAPL",
                    "change_pct": 2.5,
                    "trend": "上涨",
                    "days": 7,
                    "source": "yfinance"
                }
            }
        ]

        integrated = components["integrator"].integrate(tool_results, {})
        
        # 有 price 和 change，但没有 history 和 info
        # 数据质量应该是 2/4 = 0.5
        assert integrated["metadata"]["data_quality"] == 0.5

    def test_decision_engine_scoring(self, components):
        """测试决策引擎的评分系统"""
        analysis_result = {
            "success": True,
            "data": {
                "symbol": "AAPL",
                "technical": {
                    "rsi": {
                        "value": 75,
                        "level": "超买",
                        "signal": "可能回调"
                    },
                    "macd": {
                        "signal_type": "死叉",
                        "trend": "看跌"
                    }
                },
                "change": {
                    "change_pct": -5.0
                }
            }
        }

        decision = components["decision"].generate_decision(analysis_result, {})
        
        assert decision["success"] is True
        
        # RSI超买 + MACD死叉 + 下跌，应该是偏空
        reference = decision["reference_view"]
        assert reference["view"] in ["偏空", "中性"]
        assert reference["score"] < 0.6

    def test_response_generator_structure(self, components):
        """测试响应生成器的结构完整性"""
        analysis_result = {
            "success": True,
            "data": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "price": {"current": 150.0, "currency": "USD"},
                "change": {"change_pct": 2.5, "trend": "上涨"}
            }
        }

        decision_result = {
            "success": True,
            "reference_view": {
                "view": "偏多",
                "score": 0.7,
                "description": "技术面积极"
            },
            "opportunities": ["RSI正常区间"],
            "risks": [],
            "risk_warnings": {
                "technical_risks": [],
                "market_risks": ["市场波动风险"],
                "other_risks": ["政策风险"]
            },
            "disclaimer": "仅供参考"
        }

        integrated_data = {
            "metadata": {
                "timestamp": "2024-03-05T10:00:00",
                "sources": ["yfinance"]
            }
        }

        response = components["generator"].generate(
            analysis_result,
            decision_result,
            integrated_data
        )

        assert response["success"] is True
        
        sections = response["sections"]
        assert "data_summary" in sections
        assert "technical_analysis" in sections
        assert "reference_view" in sections
        assert "risk_warnings" in sections
        
        # 检查元数据
        metadata = response["metadata"]
        assert metadata["symbol"] == "AAPL"
        assert metadata["name"] == "Apple Inc."
