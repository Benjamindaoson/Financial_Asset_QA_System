"""
增强的市场数据服务 - 多数据源交叉验证
Enhanced Market Data Service with Cross-Validation
"""
from typing import List, Dict, Optional, Tuple
import asyncio
import statistics
from datetime import datetime

from app.market.service import MarketDataService
from app.models import MarketData


class EnhancedMarketDataService(MarketDataService):
    """增强的市场数据服务，支持多数据源交叉验证"""

    CONSISTENCY_THRESHOLD = 0.01  # 1% 差异阈值

    async def get_price_with_validation(
        self, symbol: str, validate: bool = True
    ) -> Dict:
        """
        获取价格并进行多数据源验证

        Args:
            symbol: 股票代码
            validate: 是否进行交叉验证

        Returns:
            包含价格、验证状态、数据源信息的字典
        """
        if not validate:
            # 不验证时使用原有逻辑
            result = await self.get_price(symbol)
            return {
                "price": result.price,
                "currency": result.currency,
                "source": result.source,
                "timestamp": result.timestamp,
                "validated": False,
            }

        # 并行调用多个数据源
        results = await self._fetch_from_multiple_sources(symbol)

        if not results:
            return {
                "error": "所有数据源均不可用",
                "validated": False,
            }

        # 交叉验证
        validation_result = self._validate_consistency(results)

        return {
            "price": validation_result["price"],
            "currency": validation_result["currency"],
            "source": validation_result["sources"],
            "timestamp": datetime.utcnow().isoformat(),
            "validated": True,
            "consistency": validation_result["consistency"],
            "confidence": validation_result["confidence"],
            "details": validation_result["details"],
        }

    async def _fetch_from_multiple_sources(
        self, symbol: str
    ) -> List[MarketData]:
        """从多个数据源并行获取价格"""
        tasks = []

        # 尝试所有可用的数据源
        for provider in self.providers:
            task = asyncio.create_task(
                self._safe_fetch(provider, symbol)
            )
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤掉失败的结果
        valid_results = [
            r for r in results
            if isinstance(r, MarketData) and r.price is not None
        ]

        return valid_results

    async def _safe_fetch(
        self, provider, symbol: str
    ) -> Optional[MarketData]:
        """安全地从单个数据源获取数据"""
        try:
            return await provider.get_price(symbol)
        except Exception:
            return None

    def _validate_consistency(
        self, results: List[MarketData]
    ) -> Dict:
        """
        验证多个数据源的一致性

        Returns:
            包含验证结果的字典
        """
        if len(results) == 0:
            return {"error": "没有可用数据"}

        if len(results) == 1:
            # 只有一个数据源
            return {
                "price": results[0].price,
                "currency": results[0].currency,
                "sources": [results[0].source],
                "consistency": "single_source",
                "confidence": "medium",
                "details": "仅有一个数据源，无法交叉验证",
            }

        # 提取所有价格
        prices = [r.price for r in results]
        sources = [r.source for r in results]

        # 计算统计指标
        median_price = statistics.median(prices)
        mean_price = statistics.mean(prices)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0

        # 计算最大偏差
        max_deviation = max(
            abs(p - median_price) / median_price for p in prices
        )

        # 判断一致性
        if max_deviation <= self.CONSISTENCY_THRESHOLD:
            consistency = "high"
            confidence = "high"
            message = f"数据一致性良好，{len(results)}个数据源偏差 ≤ {self.CONSISTENCY_THRESHOLD*100}%"
        elif max_deviation <= 0.03:  # 3%
            consistency = "medium"
            confidence = "medium"
            message = f"数据基本一致，{len(results)}个数据源最大偏差 {max_deviation*100:.2f}%"
        else:
            consistency = "low"
            confidence = "low"
            message = f"⚠️ 数据不一致！{len(results)}个数据源最大偏差 {max_deviation*100:.2f}%，请谨慎参考"

        return {
            "price": median_price,  # 使用中位数
            "currency": results[0].currency,
            "sources": sources,
            "consistency": consistency,
            "confidence": confidence,
            "details": {
                "message": message,
                "data_points": len(results),
                "median": round(median_price, 2),
                "mean": round(mean_price, 2),
                "std_dev": round(std_dev, 2),
                "max_deviation": round(max_deviation * 100, 2),
                "individual_prices": [
                    {"source": r.source, "price": r.price}
                    for r in results
                ],
            },
        }

    async def get_enhanced_change_analysis(
        self, symbol: str, days: int = 7
    ) -> Dict:
        """
        增强的涨跌分析：不只是涨跌幅，还包括量价配合、相对强弱等

        Args:
            symbol: 股票代码
            days: 分析天数

        Returns:
            完整的涨跌分析结果
        """
        # 1. 获取历史数据
        history = await self.get_history(symbol, days=days)

        if not history.data or len(history.data) < 2:
            return {"error": "历史数据不足"}

        # 2. 计算基础涨跌幅
        first_price = history.data[0]["close"]
        last_price = history.data[-1]["close"]
        change_pct = ((last_price - first_price) / first_price) * 100

        # 3. 分析成交量变化
        volume_analysis = self._analyze_volume_pattern(history.data)

        # 4. 计算相对强弱（与大盘对比）
        relative_strength = await self._calculate_relative_strength(
            symbol, days
        )

        # 5. 识别关键事件
        key_events = await self._identify_key_events(symbol, days)

        # 6. 生成综合结论
        conclusion = self._generate_conclusion(
            change_pct, volume_analysis, relative_strength, key_events
        )

        return {
            "symbol": symbol,
            "period": f"{days}天",
            "price_change": {
                "start_price": round(first_price, 2),
                "end_price": round(last_price, 2),
                "change_amount": round(last_price - first_price, 2),
                "change_percent": round(change_pct, 2),
                "trend": "上涨" if change_pct > 0 else "下跌" if change_pct < 0 else "持平",
            },
            "volume_analysis": volume_analysis,
            "relative_strength": relative_strength,
            "key_events": key_events,
            "conclusion": conclusion,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _analyze_volume_pattern(self, data: List[Dict]) -> Dict:
        """分析成交量模式"""
        if len(data) < 2:
            return {"pattern": "数据不足"}

        # 计算平均成交量
        volumes = [d.get("volume", 0) for d in data if d.get("volume")]
        if not volumes:
            return {"pattern": "无成交量数据"}

        avg_volume = sum(volumes) / len(volumes)
        recent_volume = volumes[-1] if volumes else 0

        # 判断量价关系
        prices = [d["close"] for d in data]
        price_trend = "上涨" if prices[-1] > prices[0] else "下跌"

        if recent_volume > avg_volume * 1.5:
            volume_trend = "放量"
        elif recent_volume < avg_volume * 0.5:
            volume_trend = "缩量"
        else:
            volume_trend = "正常"

        # 量价配合分析
        if price_trend == "上涨" and volume_trend == "放量":
            pattern = "放量上涨"
            interpretation = "✅ 量价配合良好，上涨趋势健康"
        elif price_trend == "上涨" and volume_trend == "缩量":
            pattern = "缩量上涨"
            interpretation = "⚠️ 上涨动能不足，需警惕回调"
        elif price_trend == "下跌" and volume_trend == "放量":
            pattern = "放量下跌"
            interpretation = "⚠️ 恐慌性抛售，短期可能继续下跌"
        elif price_trend == "下跌" and volume_trend == "缩量":
            pattern = "缩量下跌"
            interpretation = "✅ 抛压减轻，可能接近底部"
        else:
            pattern = "震荡整理"
            interpretation = "横盘整理，等待方向选择"

        return {
            "pattern": pattern,
            "interpretation": interpretation,
            "avg_volume": int(avg_volume),
            "recent_volume": int(recent_volume),
            "volume_ratio": round(recent_volume / avg_volume, 2) if avg_volume > 0 else 0,
        }

    async def _calculate_relative_strength(
        self, symbol: str, days: int
    ) -> Dict:
        """计算相对强弱（与大盘对比）"""
        try:
            # 获取个股数据
            stock_history = await self.get_history(symbol, days=days)

            # 获取大盘数据（使用 SPY 作为大盘指数）
            market_history = await self.get_history("SPY", days=days)

            if not stock_history.data or not market_history.data:
                return {"status": "数据不足"}

            # 计算个股涨跌幅
            stock_change = (
                (stock_history.data[-1]["close"] - stock_history.data[0]["close"])
                / stock_history.data[0]["close"]
            ) * 100

            # 计算大盘涨跌幅
            market_change = (
                (market_history.data[-1]["close"] - market_history.data[0]["close"])
                / market_history.data[0]["close"]
            ) * 100

            # 相对强弱
            relative_strength = stock_change - market_change

            if relative_strength > 5:
                performance = "显著跑赢大盘"
                interpretation = f"✅ 强于大盘 {abs(relative_strength):.2f}%"
            elif relative_strength > 0:
                performance = "跑赢大盘"
                interpretation = f"✅ 强于大盘 {abs(relative_strength):.2f}%"
            elif relative_strength > -5:
                performance = "跑输大盘"
                interpretation = f"⚠️ 弱于大盘 {abs(relative_strength):.2f}%"
            else:
                performance = "显著跑输大盘"
                interpretation = f"⚠️ 弱于大盘 {abs(relative_strength):.2f}%"

            return {
                "stock_change": round(stock_change, 2),
                "market_change": round(market_change, 2),
                "relative_strength": round(relative_strength, 2),
                "performance": performance,
                "interpretation": interpretation,
            }

        except Exception:
            return {"status": "计算失败"}

    async def _identify_key_events(
        self, symbol: str, days: int
    ) -> List[Dict]:
        """识别关键事件（简化版，实际应该调用新闻API）"""
        # 这里返回模拟数据，实际应该调用新闻API或财报API
        return [
            {
                "date": "近期",
                "type": "提示",
                "description": "建议关注该股票的财报发布、重大新闻等事件",
            }
        ]

    def _generate_conclusion(
        self,
        change_pct: float,
        volume_analysis: Dict,
        relative_strength: Dict,
        key_events: List[Dict],
    ) -> str:
        """生成综合结论"""
        # 基础趋势
        if change_pct > 5:
            trend = "强势上涨"
        elif change_pct > 0:
            trend = "温和上涨"
        elif change_pct > -5:
            trend = "小幅下跌"
        else:
            trend = "大幅下跌"

        # 量价配合
        volume_pattern = volume_analysis.get("pattern", "")

        # 相对强弱
        rs_performance = relative_strength.get("performance", "")

        # 组合结论
        conclusion = f"该股票呈现{trend}态势，{volume_pattern}。"

        if rs_performance:
            conclusion += f"相对大盘表现为{rs_performance}。"

        # 添加建议
        if change_pct > 0 and "放量" in volume_pattern and "跑赢" in rs_performance:
            conclusion += " 整体表现强劲，趋势健康。"
        elif change_pct < 0 and "放量" in volume_pattern:
            conclusion += " 需警惕进一步下跌风险。"
        else:
            conclusion += " 建议持续关注后续走势。"

        return conclusion
