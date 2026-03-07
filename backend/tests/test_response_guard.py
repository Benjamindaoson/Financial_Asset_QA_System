"""
测试 ResponseGuard 验证逻辑
"""
import pytest
from app.agent.core import ResponseGuard
from app.models import ToolResult


class TestResponseGuard:
    """测试 ResponseGuard 验证逻辑"""

    def test_validate_with_matching_numbers(self):
        """测试数字匹配的情况"""
        response = "阿里巴巴当前股价为 89.52 美元，涨幅 2.3%，数据来源 yfinance"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 89.52,
                    'change_pct': 2.3,
                    'symbol': 'BABA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            )
        ]

        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_mismatched_numbers(self):
        """测试数字不匹配的情况（幻觉）"""
        response = "阿里巴巴当前股价为 150.00 美元"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 89.52,
                    'symbol': 'BABA'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            )
        ]

        assert ResponseGuard.validate(response, tool_results) is False

    def test_validate_with_tolerance(self):
        """测试容忍误差范围"""
        response = "股价约为 89.52 美元，数据来源 yfinance"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 89.52,
                    'symbol': 'BABA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            )
        ]

        # ResponseGuard 进行精确匹配，不支持容差
        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_no_tool_results(self):
        """测试无工具结果的情况"""
        response = "这是一个知识性回答，市盈率是衡量股票估值的重要指标"
        tool_results = []

        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_percentage(self):
        """测试百分比验证"""
        response = "特斯拉今日上涨 8.4%，数据来源 yfinance"

        tool_results = [
            ToolResult(
                tool="get_change",
                data={
                    'change_pct': 8.4,
                    'symbol': 'TSLA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            )
        ]

        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_multiple_numbers(self):
        """测试多个数字的验证"""
        response = "英伟达股价 850 美元，上涨 3.2%，市盈率 65，数据来源 yfinance"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 850.0,
                    'symbol': 'NVDA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            ),
            ToolResult(
                tool="get_change",
                data={
                    'change_pct': 3.2,
                    'symbol': 'NVDA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            ),
            ToolResult(
                tool="get_info",
                data={
                    'pe_ratio': 65.0,
                    'symbol': 'NVDA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            )
        ]

        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_ignores_small_numbers(self):
        """测试忽略小数字"""
        response = "这是第 1 个例子，价格为 89.52 美元，数据来源 yfinance"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 89.52,
                    'symbol': 'BABA',
                    'source': 'yfinance'
                },
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False
            )
        ]

        # 数字 1 应该被忽略，只验证 89.52
        assert ResponseGuard.validate(response, tool_results) is True

    def test_detects_financial_advice(self):
        """测试检测金融建议"""
        tool_results = [
            ToolResult(
                tool="get_price",
                data={"price": 150.0, "symbol": "AAPL"},
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False,
                error_message=None
            )
        ]

        # Should reject direct advice
        response_with_advice = "苹果股票价格是150美元，建议买入。"
        assert ResponseGuard.validate(response_with_advice, tool_results) is False

        # Should accept neutral statement
        response_neutral = "苹果股票价格是150美元。"
        assert ResponseGuard.validate(response_neutral, tool_results) is True

    def test_requires_uncertainty_for_predictions(self):
        """测试预测需要不确定性标记"""
        tool_results = [
            ToolResult(
                tool="get_price",
                data={"price": 150.0, "symbol": "AAPL"},
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False,
                error_message=None
            )
        ]

        # Should reject prediction without uncertainty
        response_certain = "苹果股票未来将会涨到200美元。"
        assert ResponseGuard.validate(response_certain, tool_results) is False

        # Should accept prediction with uncertainty (using grounded number)
        response_uncertain = "苹果股票当前价格150美元，未来可能会有波动。"
        assert ResponseGuard.validate(response_uncertain, tool_results) is True

    def test_get_safety_warnings(self):
        """测试获取安全警告"""
        tool_results = [
            ToolResult(
                tool="get_price",
                data={"price": 150.0, "symbol": "AAPL"},
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False,
                error_message=None
            )
        ]

        # Response with advice
        response_advice = "苹果股票价格是150美元，建议买入。"
        warnings = ResponseGuard.get_safety_warnings(response_advice, tool_results)
        assert len(warnings) > 0
        assert any("financial advice" in w.lower() for w in warnings)

        # Clean response
        response_clean = "苹果股票价格是150美元。"
        warnings = ResponseGuard.get_safety_warnings(response_clean, tool_results)
        assert len(warnings) == 0

    def test_detects_english_advice(self):
        """测试检测英文金融建议"""
        tool_results = [
            ToolResult(
                tool="get_price",
                data={"price": 150.0, "symbol": "AAPL"},
                latency_ms=100,
                status="success",
                data_source="yfinance",
                cache_hit=False,
                error_message=None
            )
        ]

        response = "AAPL is at $150. I recommend buying now."
        assert ResponseGuard.validate(response, tool_results) is False

