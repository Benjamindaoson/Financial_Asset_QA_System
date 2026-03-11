"""
Data Integrator - 数据整合器
整合来自多个数据源的信息
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


class DataIntegrator:
    """
    数据整合器
    
    职责：
    1. 整合工具调用结果
    2. 数据去重和清洗
    3. 计算衍生指标
    4. 构建统一数据视图
    """
    
    def integrate(
        self,
        tool_results: List[Dict[str, Any]],
        query_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        整合工具调用结果
        
        Args:
            tool_results: 工具调用结果列表
            query_context: 查询上下文（来自 QueryRouter）
            
        Returns:
            整合后的数据视图
        """
        integrated = {
            "symbols": {},
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "sources": [],
                "data_quality": 1.0
            }
        }
        
        # 按股票代码分组
        for result in tool_results:
            if not result.get("success"):
                continue
            
            tool_name = result.get("tool")
            data = result.get("data", {})
            symbol = data.get("symbol")
            
            if not symbol:
                continue
            
            # 初始化股票数据
            if symbol not in integrated["symbols"]:
                integrated["symbols"][symbol] = {
                    "symbol": symbol,
                    "name": data.get("name", symbol),
                    "price": None,
                    "change": None,
                    "history": None,
                    "info": None,
                    "technical": None
                }
            
            # 整合不同工具的数据
            if tool_name == "get_price":
                integrated["symbols"][symbol]["price"] = {
                    "current": data.get("price"),
                    "currency": data.get("currency", "USD"),
                    "source": data.get("source")
                }
            
            elif tool_name == "get_change":
                integrated["symbols"][symbol]["change"] = {
                    "days": data.get("days"),
                    "start_price": data.get("start_price"),
                    "end_price": data.get("end_price"),
                    "change_pct": data.get("change_pct"),
                    "trend": data.get("trend")
                }
            
            elif tool_name == "get_history":
                integrated["symbols"][symbol]["history"] = {
                    "days": data.get("days"),
                    "data": data.get("data", []),
                    "count": len(data.get("data", []))
                }
            
            elif tool_name == "get_info":
                integrated["symbols"][symbol]["info"] = {
                    "sector": data.get("sector"),
                    "industry": data.get("industry"),
                    "market_cap": data.get("market_cap"),
                    "pe_ratio": data.get("pe_ratio"),
                    "week_52_high": data.get("week_52_high"),
                    "week_52_low": data.get("week_52_low")
                }
            
            # 记录数据源
            source = data.get("source")
            if source and source not in integrated["metadata"]["sources"]:
                integrated["metadata"]["sources"].append(source)
        
        # 计算数据质量
        integrated["metadata"]["data_quality"] = self._calculate_data_quality(
            integrated["symbols"]
        )
        
        return integrated
    
    def _calculate_data_quality(self, symbols: Dict[str, Any]) -> float:
        """计算数据质量分数"""
        if not symbols:
            return 0.0
        
        total_score = 0.0
        total_fields = 0
        
        for symbol_data in symbols.values():
            # 检查各个字段是否有数据
            fields = ["price", "change", "history", "info"]
            for field in fields:
                total_fields += 1
                if symbol_data.get(field) is not None:
                    total_score += 1.0
        
        if total_fields == 0:
            return 0.0
        
        return total_score / total_fields
    
    def calculate_technical_indicators(
        self,
        symbol_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        计算技术指标
        
        Args:
            symbol_data: 单个股票的数据
            
        Returns:
            技术指标字典
        """
        history = symbol_data.get("history")
        if not history or not history.get("data"):
            return None
        
        from app.market.indicators import TechnicalIndicators
        
        # 提取收盘价
        prices = [point["close"] for point in history["data"]]
        
        if len(prices) < 15:
            return None
        
        # 计算指标
        rsi = TechnicalIndicators.calculate_rsi(prices)
        macd, signal, hist = TechnicalIndicators.calculate_macd(prices)
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(prices)
        
        # 解读指标
        rsi_interp = TechnicalIndicators.interpret_rsi(rsi)
        macd_interp = TechnicalIndicators.interpret_macd(macd, signal, hist)
        
        current_price = prices[-1]
        bb_interp = TechnicalIndicators.interpret_bollinger(
            current_price, upper, middle, lower
        )
        
        trend = TechnicalIndicators.calculate_trend(prices, days=7)
        
        return {
            "rsi": {
                "value": rsi,
                "level": rsi_interp["level"],
                "signal": rsi_interp["signal"],
                "description": rsi_interp["description"]
            },
            "macd": {
                "macd": macd,
                "signal": signal,
                "histogram": hist,
                "signal_type": macd_interp["signal"],
                "trend": macd_interp["trend"],
                "description": macd_interp["description"]
            },
            "bollinger": {
                "upper": upper,
                "middle": middle,
                "lower": lower,
                "position": bb_interp["position"],
                "signal": bb_interp["signal"],
                "description": bb_interp["description"]
            },
            "trend": trend
        }
