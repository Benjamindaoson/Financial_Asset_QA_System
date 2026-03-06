"""
测试 QueryRouter
"""
import pytest
from app.reasoning.query_router import QueryRouter, QueryType, AnalysisMode


class TestQueryRouter:
    """测试查询路由器"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return QueryRouter()

    def test_route_price_query(self, router):
        """测试价格查询路由"""
        result = router.route("苹果股票多少钱")

        assert result["mode"] == AnalysisMode.FAST
        assert result["query_type"] == QueryType.PRICE
        assert "AAPL" in result["symbols"]

    def test_route_change_query(self, router):
        """测试涨跌幅查询路由"""
        result = router.route("特斯拉今天涨了多少")

        assert result["mode"] == AnalysisMode.FAST
        assert result["query_type"] == QueryType.CHANGE
        assert "TSLA" in result["symbols"]

    def test_route_technical_query(self, router):
        """测试技术分析查询路由"""
        result = router.route("阿里巴巴的RSI指标怎么样")

        assert result["query_type"] == QueryType.TECHNICAL
        assert "BABA" in result["symbols"]

    def test_route_comparison_query(self, router):
        """测试对比查询路由"""
        result = router.route("苹果和特斯拉哪个好")

        assert result["mode"] == AnalysisMode.DEEP
        assert result["query_type"] == QueryType.COMPARISON

    def test_route_prediction_query(self, router):
        """测试预测查询路由"""
        result = router.route("茅台未来会涨吗")

        assert result["mode"] == AnalysisMode.DEEP
        assert result["query_type"] == QueryType.PREDICTION

    def test_extract_symbols(self, router):
        """测试股票代码提取"""
        result = router.route("AAPL和TSLA对比")

        assert "AAPL" in result["symbols"]
        assert "TSLA" in result["symbols"]

    def test_extract_chinese_names(self, router):
        """测试中文名称提取"""
        result = router.route("苹果和特斯拉")

        assert "AAPL" in result["symbols"]
        assert "TSLA" in result["symbols"]

    def test_extract_time_range_today(self, router):
        """测试时间范围提取 - 今天"""
        result = router.route("苹果今天涨了多少")

        assert result["time_range"]["days"] == 1
        assert result["time_range"]["label"] == "今天"

    def test_extract_time_range_week(self, router):
        """测试时间范围提取 - 本周"""
        result = router.route("苹果本周表现")

        assert result["time_range"]["days"] == 7
        assert result["time_range"]["label"] == "本周"

    def test_extract_time_range_custom(self, router):
        """测试时间范围提取 - 自定义天数"""
        result = router.route("苹果30天涨跌")

        assert result["time_range"]["days"] == 30

    def test_confidence_calculation(self, router):
        """测试置信度计算"""
        # 有明确股票代码和查询类型
        result = router.route("AAPL的技术分析")
        assert result["confidence"] > 0.7

        # 模糊查询
        result = router.route("股票")
        assert result["confidence"] < 0.7

    def test_knowledge_query(self, router):
        """测试知识问答路由"""
        result = router.route("什么是市盈率")

        assert result["query_type"] == QueryType.KNOWLEDGE
        assert result["mode"] == AnalysisMode.FAST
