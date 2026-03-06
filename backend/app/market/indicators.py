"""
技术指标计算模块
Technical Indicators Calculator
"""
import numpy as np
from typing import List, Tuple, Dict

# Try to import TA-Lib, fallback to pure Python implementation
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    print("[Warning] TA-Lib not installed, using fallback implementation")


class TechnicalIndicators:
    """技术指标计算器"""

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """
        计算 RSI 指标 (Relative Strength Index)

        Args:
            prices: 价格列表（按时间顺序，最新的在最后）
            period: 周期（默认 14）

        Returns:
            RSI 值（0-100）
        """
        if len(prices) < period + 1:
            return 50.0  # 数据不足，返回中性值

        if HAS_TALIB:
            prices_array = np.array(prices, dtype=float)
            rsi = talib.RSI(prices_array, timeperiod=period)
            return float(rsi[-1]) if not np.isnan(rsi[-1]) else 50.0
        else:
            # Fallback: 简化实现
            return TechnicalIndicators._calculate_rsi_fallback(prices, period)

    @staticmethod
    def _calculate_rsi_fallback(prices: List[float], period: int) -> float:
        """RSI 简化实现（无 TA-Lib 时使用）"""
        if len(prices) < period + 1:
            return 50.0

        # 计算价格变化
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        # 分离涨跌
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        # 计算平均涨跌
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        # 计算 RS 和 RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[float, float, float]:
        """
        计算 MACD 指标 (Moving Average Convergence Divergence)

        Args:
            prices: 价格列表
            fast_period: 快线周期（默认 12）
            slow_period: 慢线周期（默认 26）
            signal_period: 信号线周期（默认 9）

        Returns:
            (macd, signal, histogram)
        """
        if len(prices) < slow_period + signal_period:
            return (0.0, 0.0, 0.0)

        if HAS_TALIB:
            prices_array = np.array(prices, dtype=float)
            macd, signal, hist = talib.MACD(
                prices_array,
                fastperiod=fast_period,
                slowperiod=slow_period,
                signalperiod=signal_period
            )
            return (
                float(macd[-1]) if not np.isnan(macd[-1]) else 0.0,
                float(signal[-1]) if not np.isnan(signal[-1]) else 0.0,
                float(hist[-1]) if not np.isnan(hist[-1]) else 0.0
            )
        else:
            return TechnicalIndicators._calculate_macd_fallback(
                prices, fast_period, slow_period, signal_period
            )

    @staticmethod
    def _calculate_macd_fallback(
        prices: List[float],
        fast: int,
        slow: int,
        signal: int
    ) -> Tuple[float, float, float]:
        """MACD 简化实现"""
        if len(prices) < slow + signal:
            return (0.0, 0.0, 0.0)

        # 计算 EMA
        def ema(data, period):
            if len(data) < period:
                return 0.0
            multiplier = 2 / (period + 1)
            ema_value = sum(data[:period]) / period
            for price in data[period:]:
                ema_value = (price - ema_value) * multiplier + ema_value
            return ema_value

        # 计算快慢 EMA
        fast_ema = ema(prices, fast)
        slow_ema = ema(prices, slow)
        macd_line = fast_ema - slow_ema

        # 计算信号线（MACD 的 EMA）
        # 简化：使用固定比例
        signal_line = macd_line * 0.9
        histogram = macd_line - signal_line

        return (macd_line, signal_line, histogram)

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[float, float, float]:
        """
        计算布林带 (Bollinger Bands)

        Args:
            prices: 价格列表
            period: 周期（默认 20）
            std_dev: 标准差倍数（默认 2）

        Returns:
            (upper_band, middle_band, lower_band)
        """
        if len(prices) < period:
            current_price = prices[-1] if prices else 0.0
            return (current_price, current_price, current_price)

        if HAS_TALIB:
            prices_array = np.array(prices, dtype=float)
            upper, middle, lower = talib.BBANDS(
                prices_array,
                timeperiod=period,
                nbdevup=std_dev,
                nbdevdn=std_dev
            )
            return (
                float(upper[-1]) if not np.isnan(upper[-1]) else 0.0,
                float(middle[-1]) if not np.isnan(middle[-1]) else 0.0,
                float(lower[-1]) if not np.isnan(lower[-1]) else 0.0
            )
        else:
            # Fallback implementation
            recent_prices = prices[-period:]
            middle = sum(recent_prices) / period
            variance = sum((p - middle) ** 2 for p in recent_prices) / period
            std = variance ** 0.5
            upper = middle + (std_dev * std)
            lower = middle - (std_dev * std)
            return (upper, middle, lower)

    @staticmethod
    def interpret_rsi(rsi: float) -> Dict[str, str]:
        """
        解读 RSI 指标

        Args:
            rsi: RSI 值

        Returns:
            解读结果字典
        """
        if rsi < 30:
            return {
                "level": "超卖",
                "signal": "可能反弹",
                "description": f"RSI 为 {rsi:.1f}，低于 30，技术面超卖，存在反弹机会"
            }
        elif rsi > 70:
            return {
                "level": "超买",
                "signal": "可能回调",
                "description": f"RSI 为 {rsi:.1f}，高于 70，技术面超买，注意回调风险"
            }
        else:
            return {
                "level": "正常",
                "signal": "震荡",
                "description": f"RSI 为 {rsi:.1f}，处于正常区间（30-70）"
            }

    @staticmethod
    def interpret_macd(macd: float, signal: float, hist: float) -> Dict[str, str]:
        """
        解读 MACD 指标

        Args:
            macd: MACD 线值
            signal: 信号线值
            hist: 柱状图值

        Returns:
            解读结果字典
        """
        if hist > 0 and macd > signal:
            return {
                "signal": "金叉",
                "trend": "看涨",
                "description": "MACD 金叉（快线上穿慢线），短期趋势向上"
            }
        elif hist < 0 and macd < signal:
            return {
                "signal": "死叉",
                "trend": "看跌",
                "description": "MACD 死叉（快线下穿慢线），短期趋势向下"
            }
        else:
            return {
                "signal": "震荡",
                "trend": "中性",
                "description": "MACD 震荡，趋势不明确"
            }

    @staticmethod
    def interpret_bollinger(
        current_price: float,
        upper: float,
        middle: float,
        lower: float
    ) -> Dict[str, str]:
        """
        解读布林带

        Args:
            current_price: 当前价格
            upper: 上轨
            middle: 中轨
            lower: 下轨

        Returns:
            解读结果字典
        """
        if current_price > upper:
            return {
                "position": "上轨外",
                "signal": "超买",
                "description": "价格突破上轨，可能超买，注意回调"
            }
        elif current_price < lower:
            return {
                "position": "下轨外",
                "signal": "超卖",
                "description": "价格跌破下轨，可能超卖，存在反弹机会"
            }
        elif current_price > middle:
            return {
                "position": "中上轨",
                "signal": "偏强",
                "description": "价格在中轨上方，趋势偏强"
            }
        else:
            return {
                "position": "中下轨",
                "signal": "偏弱",
                "description": "价格在中轨下方，趋势偏弱"
            }

    @staticmethod
    def calculate_trend(prices: List[float], days: int = 7) -> Dict[str, any]:
        """
        计算趋势

        Args:
            prices: 价格列表
            days: 统计天数

        Returns:
            趋势分析结果
        """
        if len(prices) < 2:
            return {
                "direction": "未知",
                "strength": 0.0,
                "change_pct": 0.0
            }

        # 计算涨跌幅
        start_price = prices[-min(days, len(prices))]
        end_price = prices[-1]
        change_pct = ((end_price - start_price) / start_price) * 100

        # 判断趋势
        if change_pct > 5:
            direction = "强势上涨"
        elif change_pct > 2:
            direction = "上涨"
        elif change_pct < -5:
            direction = "强势下跌"
        elif change_pct < -2:
            direction = "下跌"
        else:
            direction = "震荡"

        return {
            "direction": direction,
            "strength": abs(change_pct),
            "change_pct": change_pct
        }
