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
        response = "阿里巴巴当前股价为 89.52 美元，涨幅 2.3%"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 89.52,
                    'change_pct': 2.3,
                    'symbol': 'BABA'
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
        response = "股价约为 90 美元"

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

        # 90 vs 89.52，误差 < 5%，应该通过
        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_no_tool_results(self):
        """测试无工具结果的情况"""
        response = "这是一个知识性回答，市盈率是衡量股票估值的重要指标"
        tool_results = []

        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_percentage(self):
        """测试百分比验证"""
        response = "特斯拉今日上涨 8.4%"

        tool_results = [
            ToolResult(
                tool="get_change",
                data={
                    'change_pct': 8.4,
                    'symbol': 'TSLA'
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
        response = "英伟达股价 850 美元，上涨 3.2%，市盈率 65"

        tool_results = [
            ToolResult(
                tool="get_price",
                data={
                    'price': 850.0,
                    'symbol': 'NVDA'
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
                    'symbol': 'NVDA'
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
                    'symbol': 'NVDA'
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
        response = "这是第 1 个例子，价格为 89.52 美元"

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

        # 数字 1 应该被忽略，只验证 89.52
        assert ResponseGuard.validate(response, tool_results) is True
