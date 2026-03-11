"""
智能查询路由器 - 混合查询处理和置信度评估
Smart Query Router with Hybrid Query Handling and Confidence Assessment
"""
from typing import Dict, List, Optional, Tuple
import re

from app.routing.router import QueryRouter
from app.models import RouteDecision


class EnhancedQueryRouter(QueryRouter):
    """增强的查询路由器"""

    CONFIDENCE_THRESHOLD = 0.8  # 置信度阈值

    async def classify_with_confidence(self, query: str) -> Dict:
        """
        带置信度评估的查询分类

        Args:
            query: 用户查询

        Returns:
            包含路由决策和置信度的字典
        """
        # 1. 基础分类
        route = await self.classify_async(query)

        # 2. 计算置信度
        confidence = self._calculate_confidence(query, route)

        # 3. 低置信度处理
        if confidence < self.CONFIDENCE_THRESHOLD:
            return {
                "route": "clarification_needed",
                "confidence": confidence,
                "original_route": route.query_type.value,
                "clarification": {
                    "message": "我不太确定您的问题类型，请选择：",
                    "options": self._generate_clarification_options(query, route),
                },
            }

        return {
            "route": route.query_type.value,
            "confidence": confidence,
            "entities": route.entities,
            "metadata": route.metadata,
        }

    def _calculate_confidence(self, query: str, route: RouteDecision) -> float:
        """
        计算路由决策的置信度

        Args:
            query: 用户查询
            route: 路由决策

        Returns:
            置信度分数 (0-1)
        """
        confidence = 0.5  # 基础置信度

        query_lower = query.lower()

        # 价格查询的置信度
        if route.query_type.value == "price":
            price_keywords = ["价格", "多少钱", "股价", "price"]
            if any(kw in query_lower for kw in price_keywords):
                confidence += 0.3
            if route.entities.get("symbols"):
                confidence += 0.2

        # 涨跌查询的置信度
        elif route.query_type.value == "change":
            change_keywords = ["涨", "跌", "涨幅", "跌幅", "变化"]
            if any(kw in query_lower for kw in change_keywords):
                confidence += 0.3
            if route.entities.get("symbols"):
                confidence += 0.2

        # 知识查询的置信度
        elif route.query_type.value == "knowledge":
            knowledge_keywords = ["什么是", "如何", "为什么", "区别"]
            if any(kw in query_lower for kw in knowledge_keywords):
                confidence += 0.3
            if not route.entities.get("symbols"):
                confidence += 0.2

        return min(confidence, 1.0)

    def _generate_clarification_options(
        self, query: str, route: RouteDecision
    ) -> List[Dict]:
        """生成澄清选项"""
        options = []

        # 提取可能的股票代码
        symbols = route.entities.get("symbols", [])

        if symbols:
            options.append({
                "type": "price",
                "label": f"查询 {symbols[0]} 的当前价格",
            })
            options.append({
                "type": "change",
                "label": f"查询 {symbols[0]} 的涨跌情况",
            })

        options.append({
            "type": "knowledge",
            "label": "了解相关金融知识",
        })

        return options

    def decompose_hybrid_query(self, query: str) -> List[Dict]:
        """
        拆解混合查询

        Args:
            query: 用户查询

        Returns:
            子查询列表
        """
        sub_queries = []

        # 检测多个问题（通过标点符号）
        sentences = re.split(r'[？?。！!；;]', query)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            # 单个查询，检查是否包含多个意图
            sub_queries = self._detect_multiple_intents(query)
        else:
            # 多个句子，每个句子一个子查询
            for sentence in sentences:
                sub_queries.append({
                    "query": sentence,
                    "type": self._quick_classify(sentence),
                })

        return sub_queries if len(sub_queries) > 1 else [{"query": query, "type": "single"}]

    def _detect_multiple_intents(self, query: str) -> List[Dict]:
        """检测单个查询中的多个意图"""
        sub_queries = []
        query_lower = query.lower()

        # 检测价格查询
        if any(kw in query_lower for kw in ["价格", "多少钱", "股价"]):
            sub_queries.append({
                "query": query,
                "type": "price",
                "focus": "价格",
            })

        # 检测涨跌查询
        if any(kw in query_lower for kw in ["涨", "跌", "涨幅", "跌幅"]):
            sub_queries.append({
                "query": query,
                "type": "change",
                "focus": "涨跌",
            })

        # 检测知识查询
        if any(kw in query_lower for kw in ["什么", "如何", "为什么", "市盈率", "市净率"]):
            sub_queries.append({
                "query": query,
                "type": "knowledge",
                "focus": "知识",
            })

        return sub_queries

    def _quick_classify(self, query: str) -> str:
        """快速分类（不需要异步）"""
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["价格", "多少钱", "股价"]):
            return "price"
        elif any(kw in query_lower for kw in ["涨", "跌", "涨幅", "跌幅"]):
            return "change"
        elif any(kw in query_lower for kw in ["什么", "如何", "为什么"]):
            return "knowledge"
        else:
            return "unknown"

    def merge_answers(self, results: List[Dict]) -> str:
        """
        整合多个子查询的答案

        Args:
            results: 子查询结果列表

        Returns:
            整合后的答案
        """
        if not results:
            return "抱歉，未能找到相关信息。"

        if len(results) == 1:
            return results[0].get("answer", "")

        # 多个结果，按类型组织
        merged = []

        # 1. 价格信息
        price_results = [r for r in results if r.get("type") == "price"]
        if price_results:
            merged.append("📊 价格信息：")
            for r in price_results:
                merged.append(r.get("answer", ""))

        # 2. 涨跌信息
        change_results = [r for r in results if r.get("type") == "change"]
        if change_results:
            merged.append("\n📈 涨跌分析：")
            for r in change_results:
                merged.append(r.get("answer", ""))

        # 3. 知识信息
        knowledge_results = [r for r in results if r.get("type") == "knowledge"]
        if knowledge_results:
            merged.append("\n💡 相关知识：")
            for r in knowledge_results:
                merged.append(r.get("answer", ""))

        return "\n".join(merged)
