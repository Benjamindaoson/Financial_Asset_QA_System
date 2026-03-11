"""
Fast Analyzer - 快速分析器
用于简单查询的快速响应（1-2秒）
"""
from typing import Dict, Any, Optional


class FastAnalyzer:
    """
    快速分析器
    
    职责：
    1. 处理简单查询（价格、涨跌幅）
    2. 快速生成结构化响应
    3. 1-2秒内返回结果
    
    适用场景：
    - 价格查询
    - 涨跌幅查询
    - 简单技术指标
    """
    
    def analyze(
        self,
        integrated_data: Dict[str, Any],
        query_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        快速分析
        
        Args:
            integrated_data: 整合后的数据
            query_context: 查询上下文
            
        Returns:
            分析结果
        """
        query_type = query_context.get("query_type")
        symbols = integrated_data.get("symbols", {})
        
        if not symbols:
            return {
                "success": False,
                "error": "未找到相关股票数据"
            }
        
        # 获取第一个股票的数据（快速模式通常只处理单个股票）
        symbol_key = list(symbols.keys())[0]
        symbol_data = symbols[symbol_key]
        
        # 根据查询类型生成分析
        if query_type == "price":
            return self._analyze_price(symbol_data)
        
        elif query_type == "change":
            return self._analyze_change(symbol_data)
        
        elif query_type == "technical":
            return self._analyze_technical(symbol_data)
        
        else:
            # 默认返回综合信息
            return self._analyze_summary(symbol_data)
    
    def _analyze_price(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析价格"""
        price_info = symbol_data.get("price")
        
        if not price_info or not price_info.get("current"):
            return {
                "success": False,
                "error": "价格数据不可用"
            }
        
        return {
            "success": True,
            "type": "price",
            "data": {
                "symbol": symbol_data.get("symbol"),
                "name": symbol_data.get("name"),
                "price": price_info.get("current"),
                "currency": price_info.get("currency"),
                "source": price_info.get("source")
            },
            "summary": f"{symbol_data.get('name')} 当前价格为 {price_info.get('current')} {price_info.get('currency')}"
        }
    
    def _analyze_change(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析涨跌幅"""
        change_info = symbol_data.get("change")
        price_info = symbol_data.get("price")
        
        if not change_info:
            return {
                "success": False,
                "error": "涨跌幅数据不可用"
            }
        
        change_pct = change_info.get("change_pct", 0)
        trend = change_info.get("trend", "震荡")
        days = change_info.get("days", 7)
        
        # 生成趋势描述
        if change_pct > 0:
            trend_desc = f"上涨 {abs(change_pct):.2f}%"
        elif change_pct < 0:
            trend_desc = f"下跌 {abs(change_pct):.2f}%"
        else:
            trend_desc = "持平"
        
        return {
            "success": True,
            "type": "change",
            "data": {
                "symbol": symbol_data.get("symbol"),
                "name": symbol_data.get("name"),
                "current_price": price_info.get("current") if price_info else None,
                "change_pct": change_pct,
                "trend": trend,
                "days": days,
                "start_price": change_info.get("start_price"),
                "end_price": change_info.get("end_price")
            },
            "summary": f"{symbol_data.get('name')} 近{days}天{trend_desc}，当前趋势为{trend}"
        }
    
    def _analyze_technical(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析技术指标"""
        technical = symbol_data.get("technical")
        
        if not technical:
            return {
                "success": False,
                "error": "技术指标数据不可用"
            }
        
        # 提取关键指标
        rsi = technical.get("rsi", {})
        macd = technical.get("macd", {})
        trend = technical.get("trend", {})
        
        # 生成信号
        signals = []
        
        if rsi.get("level") == "超买":
            signals.append("RSI超买，注意回调风险")
        elif rsi.get("level") == "超卖":
            signals.append("RSI超卖，可能存在反弹机会")
        
        if macd.get("signal_type") == "金叉":
            signals.append("MACD金叉，短期看涨")
        elif macd.get("signal_type") == "死叉":
            signals.append("MACD死叉，短期看跌")
        
        return {
            "success": True,
            "type": "technical",
            "data": {
                "symbol": symbol_data.get("symbol"),
                "name": symbol_data.get("name"),
                "rsi": rsi,
                "macd": macd,
                "trend": trend,
                "signals": signals
            },
            "summary": f"{symbol_data.get('name')} 技术面：{', '.join(signals) if signals else '震荡整理'}"
        }
    
    def _analyze_summary(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """综合分析摘要"""
        price_info = symbol_data.get("price")
        change_info = symbol_data.get("change")
        
        summary_parts = []
        
        # 价格
        if price_info and price_info.get("current"):
            summary_parts.append(
                f"当前价格 {price_info.get('current')} {price_info.get('currency')}"
            )
        
        # 涨跌幅
        if change_info:
            change_pct = change_info.get("change_pct", 0)
            if change_pct > 0:
                summary_parts.append(f"上涨 {abs(change_pct):.2f}%")
            elif change_pct < 0:
                summary_parts.append(f"下跌 {abs(change_pct):.2f}%")
        
        return {
            "success": True,
            "type": "summary",
            "data": {
                "symbol": symbol_data.get("symbol"),
                "name": symbol_data.get("name"),
                "price": price_info,
                "change": change_info
            },
            "summary": f"{symbol_data.get('name')} {', '.join(summary_parts)}"
        }
