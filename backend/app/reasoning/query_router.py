"""
Query Router - 查询路由器
智能分析用户查询，决定使用 Fast Mode 还是 Deep Mode
"""
from typing import Dict, Any, Literal
from enum import Enum


class QueryType(str, Enum):
    """查询类型"""
    PRICE = "price"              # 价格查询
    CHANGE = "change"            # 涨跌幅查询
    TECHNICAL = "technical"      # 技术分析
    FUNDAMENTAL = "fundamental"  # 基本面分析
    NEWS = "news"                # 新闻事件
    KNOWLEDGE = "knowledge"      # 知识问答
    COMPARISON = "comparison"    # 对比分析
    PREDICTION = "prediction"    # 预测分析


class AnalysisMode(str, Enum):
    """分析模式"""
    FAST = "fast"    # 快速模式 (1-2s)
    DEEP = "deep"    # 深度模式 (3-5s)


class QueryRouter:
    """
    查询路由器
    
    职责：
    1. 解析用户查询意图
    2. 识别查询类型
    3. 决定分析模式（Fast/Deep）
    4. 提取关键参数（股票代码、时间范围等）
    """
    
    # Fast Mode 关键词（简单查询）
    FAST_KEYWORDS = [
        "价格", "多少钱", "现价", "当前",
        "涨", "跌", "涨幅", "跌幅",
        "今天", "昨天", "本周"
    ]
    
    # Deep Mode 关键词（复杂分析）
    DEEP_KEYWORDS = [
        "分析", "评估", "建议", "推荐",
        "对比", "比较", "哪个好",
        "预测", "未来", "趋势",
        "为什么", "原因", "解释"
    ]
    
    # 股票代码模式
    STOCK_PATTERNS = [
        r'[A-Z]{2,5}(?=[^A-Z]|$)',   # 美股: AAPL, TSLA (2-5个大写字母)
        r'\b\d{6}\b',                 # A股: 600519
        r'\d{4}\.HK',                 # 港股: 0700.HK
        r'[A-Z]+-USD'                 # 加密货币: BTC-USD
    ]
    
    def route(self, query: str) -> Dict[str, Any]:
        """
        路由查询到合适的处理模式
        
        Args:
            query: 用户查询文本
            
        Returns:
            路由结果，包含：
            - mode: fast/deep
            - query_type: 查询类型
            - symbols: 提取的股票代码列表
            - time_range: 时间范围
            - confidence: 路由置信度
        """
        query_lower = query.lower()
        
        # 1. 识别查询类型
        query_type = self._identify_query_type(query_lower)
        
        # 2. 决定分析模式
        mode = self._decide_mode(query_lower, query_type)
        
        # 3. 提取股票代码
        symbols = self._extract_symbols(query)
        
        # 4. 提取时间范围
        time_range = self._extract_time_range(query_lower)
        
        # 5. 计算置信度
        confidence = self._calculate_confidence(query_lower, query_type, symbols)
        
        return {
            "mode": mode,
            "query_type": query_type,
            "symbols": symbols,
            "time_range": time_range,
            "confidence": confidence,
            "original_query": query
        }
    
    def _identify_query_type(self, query: str) -> QueryType:
        """识别查询类型"""
        # 技术分析（优先级高，因为包含专业术语）
        if any(kw in query for kw in ["rsi", "macd", "技术", "指标", "超买", "超卖"]):
            return QueryType.TECHNICAL

        # 对比分析
        if any(kw in query for kw in ["对比", "比较", "哪个好", "vs"]):
            return QueryType.COMPARISON

        # 预测分析
        if any(kw in query for kw in ["预测", "未来", "会涨", "会跌"]):
            return QueryType.PREDICTION

        # 知识问答（检查是否是纯知识问答，不包含股票代码）
        if any(kw in query for kw in ["什么是", "如何"]):
            return QueryType.KNOWLEDGE

        # 基本面分析
        if any(kw in query for kw in ["市盈率", "pe", "市值", "基本面", "财报"]):
            return QueryType.FUNDAMENTAL

        # 新闻事件
        if any(kw in query for kw in ["新闻", "消息", "事件", "公告"]):
            return QueryType.NEWS

        # 涨跌幅查询
        if any(kw in query for kw in ["涨", "跌", "涨幅", "跌幅", "变化"]):
            return QueryType.CHANGE

        # 价格查询
        if any(kw in query for kw in ["价格", "多少钱", "现价", "股价"]):
            return QueryType.PRICE

        # 默认为价格查询
        return QueryType.PRICE
    
    def _decide_mode(self, query: str, query_type: QueryType) -> AnalysisMode:
        """决定分析模式"""
        # 强制 Deep Mode 的查询类型
        if query_type in [
            QueryType.COMPARISON,
            QueryType.PREDICTION,
            QueryType.FUNDAMENTAL
        ]:
            return AnalysisMode.DEEP
        
        # 检查是否包含 Deep Mode 关键词
        deep_score = sum(1 for kw in self.DEEP_KEYWORDS if kw in query)
        fast_score = sum(1 for kw in self.FAST_KEYWORDS if kw in query)
        
        if deep_score > fast_score:
            return AnalysisMode.DEEP
        
        # 默认 Fast Mode
        return AnalysisMode.FAST
    
    def _extract_symbols(self, query: str) -> list[str]:
        """提取股票代码"""
        import re

        symbols = []

        # 中文名称映射
        name_map = {
            "苹果": "AAPL",
            "特斯拉": "TSLA",
            "阿里": "BABA",
            "阿里巴巴": "BABA",
            "腾讯": "0700.HK",
            "茅台": "600519.SS",
            "贵州茅台": "600519.SS",
            "比特币": "BTC-USD",
            "以太坊": "ETH-USD"
        }

        # 检查中文名称
        query_lower = query.lower()
        for name, symbol in name_map.items():
            if name in query_lower:
                symbols.append(symbol)

        # 提取代码模式（使用原始大小写的query）
        for pattern in self.STOCK_PATTERNS:
            matches = re.findall(pattern, query)
            symbols.extend(matches)

        # 去重
        return list(set(symbols))
    
    def _extract_time_range(self, query: str) -> Dict[str, Any]:
        """提取时间范围"""
        if "今天" in query or "今日" in query:
            return {"days": 1, "label": "今天"}
        
        if "昨天" in query:
            return {"days": 1, "label": "昨天"}
        
        if "本周" in query or "这周" in query:
            return {"days": 7, "label": "本周"}
        
        if "本月" in query or "这个月" in query:
            return {"days": 30, "label": "本月"}
        
        if "今年" in query:
            return {"days": 365, "label": "今年"}
        
        # 提取数字 + 天/周/月
        import re
        
        # X天
        match = re.search(r'(\d+)\s*天', query)
        if match:
            days = int(match.group(1))
            return {"days": days, "label": f"{days}天"}
        
        # X周
        match = re.search(r'(\d+)\s*周', query)
        if match:
            weeks = int(match.group(1))
            return {"days": weeks * 7, "label": f"{weeks}周"}
        
        # X月
        match = re.search(r'(\d+)\s*月', query)
        if match:
            months = int(match.group(1))
            return {"days": months * 30, "label": f"{months}月"}
        
        # 默认 7 天
        return {"days": 7, "label": "近7天"}
    
    def _calculate_confidence(
        self,
        query: str,
        query_type: QueryType,
        symbols: list[str]
    ) -> float:
        """计算路由置信度"""
        confidence = 0.5  # 基础置信度
        
        # 有明确股票代码，+0.3
        if symbols:
            confidence += 0.3
        
        # 查询类型明确，+0.2
        if query_type != QueryType.PRICE:
            confidence += 0.2
        
        # 查询长度合理（5-50字），+0.1
        if 5 <= len(query) <= 50:
            confidence += 0.1
        
        return min(confidence, 1.0)
