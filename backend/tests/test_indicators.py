"""
测试技术指标计算
"""
import pytest
from app.market.indicators import TechnicalIndicators


class TestTechnicalIndicators:
    """测试技术指标计算"""

    def test_calculate_rsi_uptrend(self):
        """测试上涨趋势的 RSI"""
        # 模拟上涨趋势
        prices = [100 + i * 0.5 for i in range(30)]

        rsi = TechnicalIndicators.calculate_rsi(prices)

        assert 0 <= rsi <= 100
        assert rsi > 50  # 上涨趋势，RSI 应该 > 50

    def test_calculate_rsi_downtrend(self):
        """测试下跌趋势的 RSI"""
        # 模拟下跌趋势
        prices = [100 - i * 0.5 for i in range(30)]

        rsi = TechnicalIndicators.calculate_rsi(prices)

        assert 0 <= rsi <= 100
        assert rsi < 50  # 下跌趋势，RSI 应该 < 50

    def test_calculate_rsi_insufficient_data(self):
        """测试数据不足时的 RSI"""
        prices = [100, 101, 102]  # 少于 15 个数据点

        rsi = TechnicalIndicators.calculate_rsi(prices)

        assert rsi == 50.0  # 数据不足，返回中性值

    def test_calculate_macd(self):
        """测试 MACD 计算"""
        # 模拟价格数据
        prices = [100 + i * 0.5 for i in range(50)]

        macd, signal, hist = TechnicalIndicators.calculate_macd(prices)

        assert isinstance(macd, float)
        assert isinstance(signal, float)
        assert isinstance(hist, float)
        # 上涨趋势，MACD 应该为正
        assert macd > 0

    def test_calculate_macd_insufficient_data(self):
        """测试数据不足时的 MACD"""
        prices = [100, 101, 102]

        macd, signal, hist = TechnicalIndicators.calculate_macd(prices)

        assert macd == 0.0
        assert signal == 0.0
        assert hist == 0.0

    def test_calculate_bollinger_bands(self):
        """测试布林带计算"""
        prices = [100 + i * 0.2 for i in range(30)]

        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(prices)

        assert upper > middle > lower
        assert isinstance(upper, float)
        assert isinstance(middle, float)
        assert isinstance(lower, float)

    def test_interpret_rsi_oversold(self):
        """测试 RSI 超卖解读"""
        interpretation = TechnicalIndicators.interpret_rsi(25)

        assert interpretation["level"] == "超卖"
        assert "反弹" in interpretation["signal"]
        assert "30" in interpretation["description"]

    def test_interpret_rsi_overbought(self):
        """测试 RSI 超买解读"""
        interpretation = TechnicalIndicators.interpret_rsi(75)

        assert interpretation["level"] == "超买"
        assert "回调" in interpretation["signal"]
        assert "70" in interpretation["description"]

    def test_interpret_rsi_normal(self):
        """测试 RSI 正常区间解读"""
        interpretation = TechnicalIndicators.interpret_rsi(50)

        assert interpretation["level"] == "正常"
        assert interpretation["signal"] == "震荡"

    def test_interpret_macd_golden_cross(self):
        """测试 MACD 金叉解读"""
        interpretation = TechnicalIndicators.interpret_macd(
            macd=1.5,
            signal=1.0,
            hist=0.5
        )

        assert interpretation["signal"] == "金叉"
        assert interpretation["trend"] == "看涨"

    def test_interpret_macd_death_cross(self):
        """测试 MACD 死叉解读"""
        interpretation = TechnicalIndicators.interpret_macd(
            macd=-1.5,
            signal=-1.0,
            hist=-0.5
        )

        assert interpretation["signal"] == "死叉"
        assert interpretation["trend"] == "看跌"

    def test_interpret_bollinger_above_upper(self):
        """测试价格突破上轨"""
        interpretation = TechnicalIndicators.interpret_bollinger(
            current_price=105,
            upper=100,
            middle=95,
            lower=90
        )

        assert interpretation["position"] == "上轨外"
        assert interpretation["signal"] == "超买"

    def test_interpret_bollinger_below_lower(self):
        """测试价格跌破下轨"""
        interpretation = TechnicalIndicators.interpret_bollinger(
            current_price=85,
            upper=100,
            middle=95,
            lower=90
        )

        assert interpretation["position"] == "下轨外"
        assert interpretation["signal"] == "超卖"

    def test_calculate_trend_strong_uptrend(self):
        """测试强势上涨趋势"""
        prices = [100 + i * 1.0 for i in range(10)]

        trend = TechnicalIndicators.calculate_trend(prices, days=7)

        assert trend["direction"] == "强势上涨"
        assert trend["change_pct"] > 5
        assert trend["strength"] > 5

    def test_calculate_trend_strong_downtrend(self):
        """测试强势下跌趋势"""
        prices = [100 - i * 1.0 for i in range(10)]

        trend = TechnicalIndicators.calculate_trend(prices, days=7)

        assert trend["direction"] == "强势下跌"
        assert trend["change_pct"] < -5
        assert trend["strength"] > 5

    def test_calculate_trend_sideways(self):
        """测试震荡趋势"""
        prices = [100, 101, 100, 101, 100, 101, 100]

        trend = TechnicalIndicators.calculate_trend(prices, days=7)

        assert trend["direction"] == "震荡"
        assert -2 < trend["change_pct"] < 2

    def test_calculate_trend_insufficient_data(self):
        """测试数据不足时的趋势"""
        prices = []

        trend = TechnicalIndicators.calculate_trend(prices)

        assert trend["direction"] == "未知"
        assert trend["strength"] == 0.0
        assert trend["change_pct"] == 0.0
