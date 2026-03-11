"""
增强的RAG检索系统 - 意图识别和自适应回答
Enhanced RAG Retrieval with Intent Recognition and Adaptive Answers
"""
from typing import Dict, List, Optional
from enum import Enum

from app.rag.pipeline import RAGPipeline
from app.models import KnowledgeResult, Document


class QueryIntent(str, Enum):
    """查询意图类型"""
    DEFINITION = "definition"  # 定义类："什么是市盈率"
    METHOD = "method"  # 方法类："如何计算市盈率"
    JUDGMENT = "judgment"  # 判断类："市盈率多少合理"
    COMPARISON = "comparison"  # 对比类："市盈率和市净率的区别"
    EXAMPLE = "example"  # 示例类："市盈率的例子"


class UserLevel(str, Enum):
    """用户水平"""
    BEGINNER = "beginner"  # 初级
    INTERMEDIATE = "intermediate"  # 中级
    ADVANCED = "advanced"  # 高级


class EnhancedRAGPipeline(RAGPipeline):
    """增强的RAG检索系统"""

    # 意图识别关键词
    INTENT_KEYWORDS = {
        QueryIntent.DEFINITION: ["什么是", "是什么", "定义", "含义", "意思"],
        QueryIntent.METHOD: ["如何", "怎么", "怎样", "方法", "步骤", "计算"],
        QueryIntent.JUDGMENT: ["多少", "合理", "标准", "范围", "正常", "好坏"],
        QueryIntent.COMPARISON: ["区别", "对比", "比较", "差异", "不同"],
        QueryIntent.EXAMPLE: ["例子", "示例", "案例", "举例", "比如"],
    }

    # 用户水平判断关键词
    LEVEL_INDICATORS = {
        UserLevel.BEGINNER: ["什么是", "是什么", "基础", "入门"],
        UserLevel.ADVANCED: ["深入", "详细", "原理", "机制", "高级"],
    }

    def classify_intent(self, query: str) -> QueryIntent:
        """
        识别查询意图

        Args:
            query: 用户查询

        Returns:
            查询意图类型
        """
        query_lower = query.lower()

        # 检查每种意图的关键词
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent

        # 默认返回定义类
        return QueryIntent.DEFINITION

    def estimate_user_level(self, query: str, history: Optional[List[str]] = None) -> UserLevel:
        """
        估计用户水平

        Args:
            query: 当前查询
            history: 历史查询列表

        Returns:
            用户水平
        """
        query_lower = query.lower()

        # 检查高级关键词
        if any(keyword in query_lower for keyword in self.LEVEL_INDICATORS[UserLevel.ADVANCED]):
            return UserLevel.ADVANCED

        # 检查初级关键词
        if any(keyword in query_lower for keyword in self.LEVEL_INDICATORS[UserLevel.BEGINNER]):
            return UserLevel.BEGINNER

        # 如果有历史查询，分析复杂度
        if history:
            # 简单启发式：查询越长越复杂
            avg_length = sum(len(q) for q in history) / len(history)
            if avg_length > 30:
                return UserLevel.ADVANCED
            elif avg_length < 15:
                return UserLevel.BEGINNER

        # 默认中级
        return UserLevel.INTERMEDIATE

    async def search_with_intent(
        self,
        query: str,
        intent: Optional[QueryIntent] = None,
        user_level: Optional[UserLevel] = None,
    ) -> Dict:
        """
        基于意图的智能检索

        Args:
            query: 用户查询
            intent: 查询意图（可选，自动识别）
            user_level: 用户水平（可选，自动估计）

        Returns:
            增强的检索结果
        """
        # 1. 识别意图
        if intent is None:
            intent = self.classify_intent(query)

        # 2. 估计用户水平
        if user_level is None:
            user_level = self.estimate_user_level(query)

        # 3. 执行检索
        result = await self.search(query, use_hybrid=True)

        # 4. 根据意图调整结果
        enhanced_result = self._adjust_by_intent(result, intent)

        # 5. 根据用户水平生成回答
        answer = self._generate_adaptive_answer(
            query, enhanced_result, intent, user_level
        )

        return {
            "query": query,
            "intent": intent.value,
            "user_level": user_level.value,
            "documents": [doc.model_dump() for doc in enhanced_result.documents],
            "answer": answer,
            "metadata": {
                "total_found": enhanced_result.total_found,
                "intent_confidence": self._calculate_intent_confidence(query, intent),
            },
        }

    def _adjust_by_intent(
        self, result: KnowledgeResult, intent: QueryIntent
    ) -> KnowledgeResult:
        """
        根据意图调整检索结果

        Args:
            result: 原始检索结果
            intent: 查询意图

        Returns:
            调整后的结果
        """
        if not result.documents:
            return result

        # 根据意图对文档重新评分
        scored_docs = []
        for doc in result.documents:
            content_lower = doc.content.lower()
            score = doc.score

            # 根据意图调整分数
            if intent == QueryIntent.DEFINITION:
                # 定义类：优先包含"是"、"指"、"定义为"的内容
                if any(keyword in content_lower for keyword in ["是", "指", "定义为", "含义"]):
                    score *= 1.3
            elif intent == QueryIntent.METHOD:
                # 方法类：优先包含步骤、方法的内容
                if any(keyword in content_lower for keyword in ["步骤", "方法", "计算", "如何"]):
                    score *= 1.3
            elif intent == QueryIntent.JUDGMENT:
                # 判断类：优先包含标准、范围的内容
                if any(keyword in content_lower for keyword in ["标准", "范围", "合理", "正常"]):
                    score *= 1.3
            elif intent == QueryIntent.COMPARISON:
                # 对比类：优先包含对比、区别的内容
                if any(keyword in content_lower for keyword in ["区别", "对比", "不同", "相比"]):
                    score *= 1.3

            scored_docs.append((doc, score))

        # 重新排序
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # 返回调整后的结果
        adjusted_docs = [
            Document(content=doc.content, source=doc.source, score=score)
            for doc, score in scored_docs
        ]

        return KnowledgeResult(
            documents=adjusted_docs[:result.total_found],
            total_found=result.total_found,
        )

    def _generate_adaptive_answer(
        self,
        query: str,
        result: KnowledgeResult,
        intent: QueryIntent,
        user_level: UserLevel,
    ) -> Dict:
        """
        生成自适应回答

        Args:
            query: 用户查询
            result: 检索结果
            intent: 查询意图
            user_level: 用户水平

        Returns:
            结构化的回答
        """
        if not result.documents:
            return {
                "main_answer": "抱歉，未找到相关信息。",
                "level": user_level.value,
                "suggestions": ["请尝试使用其他关键词", "或者查询更具体的问题"],
            }

        # 提取主要内容
        main_content = result.documents[0].content

        # 根据用户水平调整回答
        if user_level == UserLevel.BEGINNER:
            answer = self._generate_beginner_answer(main_content, intent)
        elif user_level == UserLevel.INTERMEDIATE:
            answer = self._generate_intermediate_answer(main_content, intent)
        else:
            answer = self._generate_advanced_answer(main_content, intent)

        # 添加相关主题
        related_topics = self._extract_related_topics(result.documents)

        return {
            "main_answer": answer,
            "level": user_level.value,
            "intent": intent.value,
            "sources": [doc.source for doc in result.documents[:3]],
            "related_topics": related_topics,
            "confidence": self._calculate_answer_confidence(result),
        }

    def _generate_beginner_answer(self, content: str, intent: QueryIntent) -> str:
        """生成初级用户回答（简单+类比）"""
        # 提取核心内容（前200字）
        core = content[:200] if len(content) > 200 else content

        answer = f"💡 简单来说：\n\n{core}\n\n"

        # 根据意图添加说明
        if intent == QueryIntent.DEFINITION:
            answer += "📌 通俗理解：这是一个基础的金融概念，理解它可以帮助您更好地分析投资。"
        elif intent == QueryIntent.METHOD:
            answer += "📌 实用提示：按照上述步骤操作即可，不需要复杂的计算。"

        return answer

    def _generate_intermediate_answer(self, content: str, intent: QueryIntent) -> str:
        """生成中级用户回答（标准+示例）"""
        answer = f"{content}\n\n"

        # 根据意图添加补充
        if intent == QueryIntent.DEFINITION:
            answer += "💡 应用场景：这个指标常用于股票估值和投资决策。"
        elif intent == QueryIntent.METHOD:
            answer += "💡 注意事项：实际应用时需要结合具体情况调整。"
        elif intent == QueryIntent.JUDGMENT:
            answer += "💡 参考标准：不同行业和市场环境下，合理范围可能有所不同。"

        return answer

    def _generate_advanced_answer(self, content: str, intent: QueryIntent) -> str:
        """生成高级用户回答（深入+注意事项）"""
        answer = f"{content}\n\n"

        # 添加深度分析
        answer += "🔍 深度分析：\n"

        if intent == QueryIntent.DEFINITION:
            answer += "- 该概念的理论基础和发展历史\n"
            answer += "- 在现代金融理论中的地位\n"
            answer += "- 与其他相关概念的联系\n"
        elif intent == QueryIntent.METHOD:
            answer += "- 方法的理论依据和适用条件\n"
            answer += "- 可能的局限性和改进方向\n"
            answer += "- 实际应用中的常见问题\n"
        elif intent == QueryIntent.JUDGMENT:
            answer += "- 判断标准的理论基础\n"
            answer += "- 不同市场环境下的调整\n"
            answer += "- 需要注意的特殊情况\n"

        return answer

    def _extract_related_topics(self, documents: List[Document]) -> List[str]:
        """提取相关主题"""
        # 简化版：从文档源提取
        topics = set()
        for doc in documents[:5]:
            # 从文件名提取主题
            source = doc.source.replace(".md", "").replace("_", " ")
            topics.add(source)

        return list(topics)[:5]

    def _calculate_intent_confidence(self, query: str, intent: QueryIntent) -> float:
        """计算意图识别的置信度"""
        query_lower = query.lower()
        keywords = self.INTENT_KEYWORDS.get(intent, [])

        # 计算匹配的关键词数量
        matches = sum(1 for keyword in keywords if keyword in query_lower)

        if matches >= 2:
            return 0.9
        elif matches == 1:
            return 0.7
        else:
            return 0.5

    def _calculate_answer_confidence(self, result: KnowledgeResult) -> str:
        """计算回答的置信度"""
        if not result.documents:
            return "low"

        # 基于检索分数判断
        top_score = result.documents[0].score

        if top_score > 0.8:
            return "high"
        elif top_score > 0.5:
            return "medium"
        else:
            return "low"
