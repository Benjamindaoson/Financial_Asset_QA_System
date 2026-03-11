"""
友好的错误处理器 - 提供建议而不只是报错
Friendly Error Handler with Suggestions
"""
from typing import Dict, List, Optional
import difflib


class FriendlyErrorHandler:
    """友好的错误处理器"""

    # 常见股票代码映射
    COMMON_SYMBOLS = {
        "苹果": "AAPL",
        "特斯拉": "TSLA",
        "微软": "MSFT",
        "谷歌": "GOOGL",
        "亚马逊": "AMZN",
        "阿里巴巴": "BABA",
        "腾讯": "0700.HK",
        "茅台": "600519.SS",
        "比特币": "BTC-USD",
    }

    def handle_symbol_not_found(self, query: str) -> Dict:
        """
        处理股票代码未找到错误

        Args:
            query: 用户查询

        Returns:
            友好的错误信息和建议
        """
        # 尝试从查询中提取可能的股票名称
        possible_name = self._extract_stock_name(query)

        # 查找相似的股票代码
        suggestions = self._find_similar_symbols(possible_name)

        return {
            "error": "symbol_not_found",
            "message": f"未找到股票：{possible_name}",
            "suggestions": suggestions,
            "help": {
                "title": "您可以尝试：",
                "options": [
                    f"使用标准股票代码（如 AAPL、TSLA）",
                    f"使用中文名称（如 苹果、特斯拉）",
                    f"检查拼写是否正确",
                ],
            },
            "examples": [
                "AAPL最新价格",
                "特斯拉股价",
                "600519.SS涨跌情况",
            ],
        }

    def handle_data_unavailable(self, symbol: str, reason: Optional[str] = None) -> Dict:
        """
        处理数据不可用错误

        Args:
            symbol: 股票代码
            reason: 原因

        Returns:
            友好的错误信息
        """
        return {
            "error": "data_unavailable",
            "message": f"{symbol} 的数据暂时不可用",
            "reason": reason or "数据源可能正在维护，或该股票已退市",
            "suggestions": [
                "稍后再试",
                "查询其他股票",
                "使用历史数据查询",
            ],
            "alternative": {
                "title": "您可能感兴趣的其他股票：",
                "symbols": self._suggest_alternative_symbols(symbol),
            },
        }

    def handle_rate_limit(self) -> Dict:
        """处理API限流错误"""
        return {
            "error": "rate_limit",
            "message": "查询过于频繁，请稍后再试",
            "reason": "为了保证服务质量，我们限制了查询频率",
            "suggestions": [
                "等待 1 分钟后重试",
                "减少查询频率",
                "考虑升级到专业版（无限制）",
            ],
            "retry_after": 60,  # 秒
        }

    def handle_invalid_query(self, query: str) -> Dict:
        """
        处理无效查询

        Args:
            query: 用户查询

        Returns:
            友好的错误信息和示例
        """
        return {
            "error": "invalid_query",
            "message": "抱歉，我没有理解您的问题",
            "suggestions": [
                "请尝试更具体的问题",
                "参考下面的示例",
            ],
            "examples": {
                "价格查询": [
                    "AAPL最新价格",
                    "特斯拉现在多少钱",
                ],
                "涨跌查询": [
                    "AAPL最近7天涨跌",
                    "特斯拉今天涨了多少",
                ],
                "知识查询": [
                    "什么是市盈率",
                    "如何计算市净率",
                ],
            },
        }

    def handle_network_error(self) -> Dict:
        """处理网络错误"""
        return {
            "error": "network_error",
            "message": "网络连接失败",
            "reason": "无法连接到数据源服务器",
            "suggestions": [
                "检查网络连接",
                "稍后重试",
                "使用缓存数据（如果可用）",
            ],
            "status": "degraded",
        }

    def _extract_stock_name(self, query: str) -> str:
        """从查询中提取股票名称"""
        # 移除常见的查询词
        noise_words = ["的", "股票", "价格", "多少钱", "涨跌", "怎么样"]
        cleaned = query
        for word in noise_words:
            cleaned = cleaned.replace(word, "")

        return cleaned.strip()

    def _find_similar_symbols(self, name: str) -> List[Dict]:
        """查找相似的股票代码"""
        suggestions = []

        # 1. 精确匹配
        if name in self.COMMON_SYMBOLS:
            suggestions.append({
                "symbol": self.COMMON_SYMBOLS[name],
                "name": name,
                "confidence": "high",
                "reason": "精确匹配",
            })
            return suggestions

        # 2. 模糊匹配
        matches = difflib.get_close_matches(
            name.lower(),
            [k.lower() for k in self.COMMON_SYMBOLS.keys()],
            n=3,
            cutoff=0.6,
        )

        for match in matches:
            # 找到原始的键
            original_key = next(
                k for k in self.COMMON_SYMBOLS.keys()
                if k.lower() == match
            )
            suggestions.append({
                "symbol": self.COMMON_SYMBOLS[original_key],
                "name": original_key,
                "confidence": "medium",
                "reason": "相似匹配",
            })

        # 3. 如果没有匹配，返回热门股票
        if not suggestions:
            suggestions = [
                {
                    "symbol": "AAPL",
                    "name": "苹果",
                    "confidence": "low",
                    "reason": "热门股票推荐",
                },
                {
                    "symbol": "TSLA",
                    "name": "特斯拉",
                    "confidence": "low",
                    "reason": "热门股票推荐",
                },
            ]

        return suggestions

    def _suggest_alternative_symbols(self, symbol: str) -> List[Dict]:
        """建议替代股票"""
        # 简化实现：返回热门股票
        return [
            {"symbol": "AAPL", "name": "苹果"},
            {"symbol": "TSLA", "name": "特斯拉"},
            {"symbol": "MSFT", "name": "微软"},
        ]


class SmartDegradation:
    """智能降级处理"""

    def __init__(self):
        self.cache = {}  # 简化的缓存

    def degrade_gracefully(self, query: str, error_type: str) -> Dict:
        """
        优雅降级

        Args:
            query: 用户查询
            error_type: 错误类型

        Returns:
            降级后的响应
        """
        if error_type == "llm_unavailable":
            return self._handle_llm_unavailable(query)
        elif error_type == "market_api_unavailable":
            return self._handle_market_api_unavailable(query)
        elif error_type == "partial_failure":
            return self._handle_partial_failure(query)
        else:
            return self._handle_unknown_error(query)

    def _handle_llm_unavailable(self, query: str) -> Dict:
        """处理LLM不可用"""
        # 使用模板回答
        template_answer = self._get_template_answer(query)

        return {
            "answer": template_answer,
            "mode": "template",
            "warning": "⚠️ AI服务暂时不可用，使用模板回答",
            "suggestion": "功能受限，建议稍后重试以获得更好的体验",
        }

    def _handle_market_api_unavailable(self, query: str) -> Dict:
        """处理市场API不可用"""
        # 尝试使用缓存数据
        cached_data = self._get_cached_data(query)

        if cached_data:
            return {
                "answer": cached_data["answer"],
                "mode": "cached",
                "warning": "⚠️ 实时数据不可用，使用缓存数据",
                "cache_time": cached_data.get("timestamp", "未知"),
                "suggestion": "数据可能不是最新的，建议稍后重试",
            }
        else:
            return {
                "answer": "抱歉，当前无法获取实时数据，且没有可用的缓存数据。",
                "mode": "unavailable",
                "warning": "⚠️ 数据服务暂时不可用",
                "suggestion": "请稍后重试，或查询其他股票",
            }

    def _handle_partial_failure(self, query: str) -> Dict:
        """处理部分功能失败"""
        return {
            "answer": "部分功能暂时不可用，但基础查询仍然可用。",
            "mode": "partial",
            "available_features": [
                "价格查询（使用缓存）",
                "知识问答（本地知识库）",
            ],
            "unavailable_features": [
                "实时新闻分析",
                "高级技术指标",
            ],
            "suggestion": "您可以继续使用可用功能，或稍后重试以使用完整功能",
        }

    def _handle_unknown_error(self, query: str) -> Dict:
        """处理未知错误"""
        return {
            "answer": "抱歉，系统遇到了未知错误。",
            "mode": "error",
            "suggestion": "请稍后重试，或联系技术支持",
            "support": {
                "email": "support@example.com",
                "docs": "https://docs.example.com",
            },
        }

    def _get_template_answer(self, query: str) -> str:
        """获取模板回答"""
        query_lower = query.lower()

        if "价格" in query_lower or "多少钱" in query_lower:
            return "您可以通过查看实时行情获取最新价格信息。"
        elif "涨跌" in query_lower:
            return "您可以查看K线图了解涨跌情况。"
        elif "什么是" in query_lower:
            return "这是一个金融术语，建议查阅相关资料了解详情。"
        else:
            return "抱歉，当前无法提供详细回答。"

    def _get_cached_data(self, query: str) -> Optional[Dict]:
        """获取缓存数据"""
        # 简化实现
        return self.cache.get(query)
