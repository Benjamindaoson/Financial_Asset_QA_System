"""Technical analysis indicators calculator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from app.models import PricePoint


class TechnicalAnalyzer:
    """Calculate technical and return/risk indicators from price history."""

    @staticmethod
    def calculate_ma(data: List[PricePoint], period: int) -> Optional[float]:
        if len(data) < period:
            return None
        prices = [point.close for point in data[-period:]]
        return round(sum(prices) / period, 2)

    @staticmethod
    def calculate_rsi(data: List[PricePoint], period: int = 14) -> Optional[float]:
        if len(data) < period + 1:
            return None
        prices = [point.close for point in data]
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)

    @staticmethod
    def calculate_macd(data: List[PricePoint]) -> Optional[Dict[str, float]]:
        if len(data) < 26:
            return None
        prices = [point.close for point in data]

        def ema(series: List[float], period: int) -> float:
            multiplier = 2 / (period + 1)
            current = series[0]
            for price in series[1:]:
                current = (price - current) * multiplier + current
            return current

        ema12 = ema(prices, 12)
        ema26 = ema(prices, 26)
        macd_line = ema12 - ema26
        signal = macd_line * 0.9
        return {
            "macd": round(macd_line, 2),
            "signal": round(signal, 2),
            "histogram": round(macd_line - signal, 2),
        }

    @staticmethod
    def find_support_resistance(data: List[PricePoint]) -> Dict[str, Optional[float]]:
        if len(data) < 20:
            return {"support": None, "resistance": None}
        highs = [point.high for point in data[-20:]]
        lows = [point.low for point in data[-20:]]
        return {"support": round(min(lows), 2), "resistance": round(max(highs), 2)}

    @staticmethod
    def identify_trend(data: List[PricePoint]) -> str:
        if len(data) < 20:
            return "insufficient_data"
        ma5 = TechnicalAnalyzer.calculate_ma(data, 5)
        ma20 = TechnicalAnalyzer.calculate_ma(data, 20)
        if ma5 is None or ma20 is None:
            return "insufficient_data"
        current_price = data[-1].close
        if ma5 > ma20 and current_price > ma5:
            return "uptrend"
        if ma5 < ma20 and current_price < ma5:
            return "downtrend"
        return "sideways"

    @staticmethod
    def analyze_volume(data: List[PricePoint]) -> Dict[str, Any]:
        if len(data) < 20:
            return {"status": "insufficient_data"}
        volumes = [point.volume for point in data]
        avg_volume = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]
        ratio = current_volume / avg_volume if avg_volume else 1.0
        return {
            "current": current_volume,
            "average": int(avg_volume),
            "ratio": round(ratio, 2),
            "status": "high" if ratio > 1.5 else "low" if ratio < 0.5 else "normal",
        }

    @staticmethod
    def calculate_risk_metrics(data: List[PricePoint]) -> Dict[str, Optional[float]]:
        if len(data) < 2:
            return {
                "annualized_volatility": None,
                "total_return_pct": None,
                "max_drawdown_pct": None,
            }
        closes = np.array([point.close for point in data], dtype=float)
        returns = np.diff(closes) / closes[:-1]
        volatility = float(np.std(returns, ddof=1)) * np.sqrt(252) * 100 if len(returns) > 1 else 0.0
        total_return = ((closes[-1] / closes[0]) - 1.0) * 100 if closes[0] else 0.0
        cumulative = np.cumprod(1 + returns)
        peaks = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative / peaks) - 1.0
        max_drawdown = float(drawdowns.min()) * 100 if len(drawdowns) else 0.0
        return {
            "annualized_volatility": round(volatility, 2),
            "total_return_pct": round(total_return, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
        }

    def analyze(self, data: List[PricePoint]) -> Dict[str, Any]:
        if len(data) < 20:
            return {"error": "Insufficient data for technical analysis"}

        rsi = self.calculate_rsi(data)
        rsi_signal = "neutral"
        if rsi is not None:
            if rsi > 70:
                rsi_signal = "overbought"
            elif rsi < 30:
                rsi_signal = "oversold"

        support_resistance = self.find_support_resistance(data)
        risk = self.calculate_risk_metrics(data)
        return {
            "current_price": data[-1].close,
            "ma5": self.calculate_ma(data, 5),
            "ma20": self.calculate_ma(data, 20),
            "rsi": rsi,
            "rsi_signal": rsi_signal,
            "macd": self.calculate_macd(data),
            "support": support_resistance["support"],
            "resistance": support_resistance["resistance"],
            "trend": self.identify_trend(data),
            "volume": self.analyze_volume(data),
            **risk,
        }
