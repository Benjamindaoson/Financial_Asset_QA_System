"""
增强的Agent核心 - 集成所有高级功能
Enhanced Agent Core with All Advanced Features
"""
from typing import AsyncGenerator, Dict, List, Optional
import asyncio

from app.agent.core import AgentCore
from app.market.enhanced_service import EnhancedMarketDataService
from app.rag.enhanced_pipeline import EnhancedRAGPipeline
from app.rag.grounded_pipeline import GroundedRAGPipeline
from app.rag.fact_verifier import AnswerQualityController
from app.routing.enhanced_router import EnhancedQueryRouter
from app.formatting.smart_formatter import SmartFormatter
from app.errors.friendly_handler import FriendlyErrorHandler, SmartDegradation
from app.models import StreamEvent


class EnhancedAgentCore(AgentCore):
    """
    增强的Agent核心
    集成了所有高级功能：
    1. 多数据源交叉验证
    2. 深度涨跌分析
    3. 意图识别和自适应回答
    4. 混合查询处理
    5. 智能格式化
    6. 友好错误处理
    """

    def __init__(self):
        super().__init__()

        # 使用增强版服务
        self.enhanced_market_service = EnhancedMarketDataService()
        self.enhanced_rag_pipeline = EnhancedRAGPipeline()
        self.grounded_rag_pipeline = GroundedRAGPipeline()  # 基于事实的RAG
        self.quality_controller = AnswerQualityController()  # 答案质量控制
        self.enhanced_router = EnhancedQueryRouter()
        self.smart_formatter = SmartFormatter()
        self.error_handler = FriendlyErrorHandler()
        self.degradation = SmartDegradation()

    async def run_enhanced(
        self,
        query: str,
        model_name: Optional[str] = None,
        enable_validation: bool = True,
        enable_intent_recognition: bool = True,
        enable_fact_checking: bool = True,  # 新增：启用事实检查
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        增强的运行方法

        Args:
            query: 用户查询
            model_name: 模型名称
            enable_validation: 是否启用数据验证
            enable_intent_recognition: 是否启用意图识别

        Yields:
            流式事件
        """
        try:
            # 1. 增强的查询路由（带置信度评估）
            yield StreamEvent(type="status", text="🔍 智能分析查询意图...")

            route_result = await self.enhanced_router.classify_with_confidence(query)

            # 如果需要澄清
            if route_result.get("route") == "clarification_needed":
                yield StreamEvent(
                    type="clarification",
                    data=route_result.get("clarification"),
                )
                return

            route_type = route_result.get("route")
            confidence = route_result.get("confidence", 0)

            yield StreamEvent(
                type="route_decision",
                data={
                    "route": route_type,
                    "confidence": confidence,
                    "message": f"识别为{route_type}类查询（置信度: {confidence:.0%}）",
                },
            )

            # 2. 检查是否为混合查询
            sub_queries = self.enhanced_router.decompose_hybrid_query(query)

            if len(sub_queries) > 1:
                # 处理混合查询
                yield StreamEvent(type="status", text="📋 检测到复合查询，正在分别处理...")

                results = await self._handle_hybrid_query(sub_queries, enable_validation)

                # 整合答案
                merged_answer = self.enhanced_router.merge_answers(results)

                yield StreamEvent(type="chunk", text=merged_answer)
                yield StreamEvent(type="done", data={"hybrid": True})
                return

            # 3. 根据路由类型处理
            if route_type == "price":
                async for event in self._handle_price_query_enhanced(
                    query, route_result, enable_validation
                ):
                    yield event

            elif route_type == "change":
                async for event in self._handle_change_query_enhanced(
                    query, route_result, enable_validation
                ):
                    yield event

            elif route_type == "knowledge":
                async for event in self._handle_knowledge_query_enhanced(
                    query, enable_intent_recognition, enable_fact_checking
                ):
                    yield event

            else:
                # 使用原有逻辑
                async for event in super().run(query, model_name):
                    yield event

        except Exception as e:
            # 友好的错误处理
            error_response = self._handle_error_friendly(e, query)
            yield StreamEvent(type="error", data=error_response)

    async def _handle_price_query_enhanced(
        self,
        query: str,
        route_result: Dict,
        enable_validation: bool,
    ) -> AsyncGenerator[StreamEvent, None]:
        """增强的价格查询处理"""
        symbols = route_result.get("entities", {}).get("symbols", [])

        if not symbols:
            yield StreamEvent(type="error", text="未能识别股票代码")
            return

        symbol = symbols[0]

        yield StreamEvent(
            type="tool_start",
            data={"name": "get_price_validated", "symbol": symbol},
        )

        try:
            # 使用多数据源验证
            result = await self.enhanced_market_service.get_price_with_validation(
                symbol, validate=enable_validation
            )

            if "error" in result:
                # 友好的错误处理
                error_response = self.error_handler.handle_symbol_not_found(query)
                yield StreamEvent(type="error", data=error_response)
                return

            # 智能格式化
            formatted = self.smart_formatter.format_answer(query, result)

            # 生成回答
            answer = self._generate_price_answer(symbol, result)

            yield StreamEvent(type="tool_data", data=result)
            yield StreamEvent(type="chunk", text=answer)

            # 如果启用了验证，显示验证信息
            if enable_validation and result.get("validated"):
                validation_msg = self._format_validation_message(result)
                yield StreamEvent(type="chunk", text=f"\n\n{validation_msg}")

            yield StreamEvent(
                type="done",
                data={
                    "formatted": formatted,
                    "confidence": result.get("confidence", "medium"),
                },
            )

        except Exception as e:
            error_response = self.error_handler.handle_data_unavailable(symbol, str(e))
            yield StreamEvent(type="error", data=error_response)

    async def _handle_change_query_enhanced(
        self,
        query: str,
        route_result: Dict,
        enable_validation: bool,
    ) -> AsyncGenerator[StreamEvent, None]:
        """增强的涨跌查询处理"""
        symbols = route_result.get("entities", {}).get("symbols", [])

        if not symbols:
            yield StreamEvent(type="error", text="未能识别股票代码")
            return

        symbol = symbols[0]
        days = route_result.get("entities", {}).get("days", 7)

        yield StreamEvent(
            type="tool_start",
            data={"name": "get_enhanced_change_analysis", "symbol": symbol, "days": days},
        )

        try:
            # 使用增强的涨跌分析
            result = await self.enhanced_market_service.get_enhanced_change_analysis(
                symbol, days=days
            )

            if "error" in result:
                error_response = self.error_handler.handle_data_unavailable(symbol)
                yield StreamEvent(type="error", data=error_response)
                return

            # 智能格式化
            formatted = self.smart_formatter.format_answer(query, result)

            # 生成详细回答
            answer = self._generate_change_answer(symbol, result)

            yield StreamEvent(type="tool_data", data=result)
            yield StreamEvent(type="chunk", text=answer)
            yield StreamEvent(
                type="done",
                data={"formatted": formatted, "analysis_depth": "enhanced"},
            )

        except Exception as e:
            error_response = self.error_handler.handle_data_unavailable(symbol, str(e))
            yield StreamEvent(type="error", data=error_response)

    async def _handle_knowledge_query_enhanced(
        self,
        query: str,
        enable_intent_recognition: bool,
        enable_fact_checking: bool = True,
    ) -> AsyncGenerator[StreamEvent, None]:
        """增强的知识查询处理（带事实检查）"""
        yield StreamEvent(
            type="tool_start",
            data={"name": "search_with_grounding", "query": query},
        )

        try:
            if enable_fact_checking:
                # 使用基于事实的RAG管道（防止幻觉）
                yield StreamEvent(type="status", text="🔍 检索知识库并验证事实...")

                result = await self.grounded_rag_pipeline.search_grounded(
                    query,
                    require_sources=True
                )

                # 检查是否能回答
                if not result.get("can_answer", True):
                    # 无法回答，返回友好提示
                    yield StreamEvent(type="chunk", text=result["answer"])

                    suggestions = result.get("suggestions", [])
                    if suggestions:
                        suggestions_text = "\n\n💡 建议：\n" + "\n".join(f"- {s}" for s in suggestions)
                        yield StreamEvent(type="chunk", text=suggestions_text)

                    yield StreamEvent(
                        type="done",
                        data={
                            "can_answer": False,
                            "reason": result.get("reason"),
                            "grounded": True
                        }
                    )
                    return

                # 有答案，进行质量控制
                quality_result = self.quality_controller.check_and_control(
                    answer=result["answer"],
                    source_documents=result["sources"],
                    query=query,
                    min_confidence=0.7
                )

                # 返回质量控制后的答案
                final_answer = quality_result["answer"]

                yield StreamEvent(type="tool_data", data=result)
                yield StreamEvent(type="chunk", text=final_answer)

                # 显示来源
                sources = result.get("sources", [])
                if sources and quality_result["passed_quality_check"]:
                    sources_text = "\n\n📚 参考来源：\n"
                    for source in sources[:3]:  # 最多显示3个来源
                        sources_text += f"[文档{source['id']}] {source['content'][:100]}...\n"
                    yield StreamEvent(type="chunk", text=sources_text)

                # 显示质量验证信息
                if not quality_result["passed_quality_check"]:
                    warning_text = "\n\n⚠️ 为确保准确性，已使用原文档内容回答"
                    yield StreamEvent(type="chunk", text=warning_text)

                yield StreamEvent(
                    type="done",
                    data={
                        "grounded": True,
                        "confidence": result.get("confidence"),
                        "quality_check_passed": quality_result["passed_quality_check"],
                        "verification": quality_result.get("verification_details"),
                    }
                )

            elif enable_intent_recognition:
                # 使用意图识别和自适应回答（原有逻辑）
                result = await self.enhanced_rag_pipeline.search_with_intent(query)

                yield StreamEvent(
                    type="intent_recognized",
                    data={
                        "intent": result.get("intent"),
                        "user_level": result.get("user_level"),
                    },
                )

                # 提取回答
                answer_data = result.get("answer", {})
                main_answer = answer_data.get("main_answer", "未找到相关信息")

                yield StreamEvent(type="tool_data", data=result)
                yield StreamEvent(type="chunk", text=main_answer)

                # 显示相关主题
                related_topics = answer_data.get("related_topics", [])
                if related_topics:
                    topics_text = "\n\n💡 相关主题：" + "、".join(related_topics)
                    yield StreamEvent(type="chunk", text=topics_text)

                yield StreamEvent(
                    type="done",
                    data={
                        "intent": result.get("intent"),
                        "confidence": answer_data.get("confidence", "medium"),
                    },
                )
            else:
                # 使用基础检索
                basic_result = await self.enhanced_rag_pipeline.search(query)
                result = {
                    "answer": {"main_answer": "基础检索结果"},
                    "documents": [doc.model_dump() for doc in basic_result.documents],
                }

                # 提取回答
                answer_data = result.get("answer", {})
                main_answer = answer_data.get("main_answer", "未找到相关信息")

                yield StreamEvent(type="tool_data", data=result)
                yield StreamEvent(type="chunk", text=main_answer)

                yield StreamEvent(
                    type="done",
                    data={
                        "confidence": answer_data.get("confidence", "medium"),
                    },
                )

        except Exception as e:
            error_response = self.error_handler.handle_invalid_query(query)
            yield StreamEvent(type="error", data=error_response)

    async def _handle_hybrid_query(
        self,
        sub_queries: List[Dict],
        enable_validation: bool,
    ) -> List[Dict]:
        """处理混合查询"""
        tasks = []

        for sub_query in sub_queries:
            query_text = sub_query.get("query")
            query_type = sub_query.get("type")

            if query_type == "price":
                task = self._get_price_result(query_text, enable_validation)
            elif query_type == "change":
                task = self._get_change_result(query_text, enable_validation)
            elif query_type == "knowledge":
                task = self._get_knowledge_result(query_text)
            else:
                continue

            tasks.append(task)

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤掉异常
        valid_results = [r for r in results if not isinstance(r, Exception)]

        return valid_results

    async def _get_price_result(self, query: str, enable_validation: bool) -> Dict:
        """获取价格结果"""
        try:
            # 提取股票代码
            route = await self.enhanced_router.classify_with_confidence(query)
            symbols = route.get("entities", {}).get("symbols", [])

            if not symbols:
                return {"type": "price", "answer": "未能识别股票代码"}

            symbol = symbols[0]
            result = await self.enhanced_market_service.get_price_with_validation(
                symbol, validate=enable_validation
            )

            if "error" in result:
                return {"type": "price", "answer": f"无法获取{symbol}的价格信息"}

            price = result.get("price")
            currency = result.get("currency", "USD")
            answer = f"{symbol} 当前价格：{price} {currency}"

            return {"type": "price", "answer": answer}
        except Exception as e:
            return {"type": "price", "answer": f"价格查询失败：{str(e)}"}

    async def _get_change_result(self, query: str, enable_validation: bool) -> Dict:
        """获取涨跌结果"""
        try:
            # 提取股票代码
            route = await self.enhanced_router.classify_with_confidence(query)
            symbols = route.get("entities", {}).get("symbols", [])
            days = route.get("entities", {}).get("days", 7)

            if not symbols:
                return {"type": "change", "answer": "未能识别股票代码"}

            symbol = symbols[0]
            result = await self.enhanced_market_service.get_enhanced_change_analysis(
                symbol, days=days
            )

            if "error" in result:
                return {"type": "change", "answer": f"无法获取{symbol}的涨跌信息"}

            price_change = result.get("price_change", {})
            change_pct = price_change.get("change_percent", 0)
            answer = f"{symbol} 涨跌幅：{change_pct:+.2f}%"

            return {"type": "change", "answer": answer}
        except Exception as e:
            return {"type": "change", "answer": f"涨跌查询失败：{str(e)}"}

    async def _get_knowledge_result(self, query: str) -> Dict:
        """获取知识结果"""
        try:
            result = await self.enhanced_rag_pipeline.search_with_intent(query)
            answer_data = result.get("answer", {})
            main_answer = answer_data.get("main_answer", "未找到相关信息")

            return {"type": "knowledge", "answer": main_answer}
        except Exception as e:
            return {"type": "knowledge", "answer": f"知识查询失败：{str(e)}"}

    def _generate_price_answer(self, symbol: str, result: Dict) -> str:
        """生成价格回答"""
        price = result.get("price")
        currency = result.get("currency", "USD")

        answer = f"📊 {symbol} 当前价格：{price} {currency}"

        return answer

    def _generate_change_answer(self, symbol: str, result: Dict) -> str:
        """生成涨跌回答"""
        price_change = result.get("price_change", {})
        volume_analysis = result.get("volume_analysis", {})
        relative_strength = result.get("relative_strength", {})
        conclusion = result.get("conclusion", "")

        answer = f"📈 {symbol} 涨跌分析：\n\n"

        # 价格变化
        change_pct = price_change.get("change_percent", 0)
        answer += f"涨跌幅：{change_pct:+.2f}%\n"

        # 量价分析
        pattern = volume_analysis.get("pattern", "")
        interpretation = volume_analysis.get("interpretation", "")
        if pattern:
            answer += f"\n{interpretation}\n"

        # 相对强弱
        rs_interpretation = relative_strength.get("interpretation", "")
        if rs_interpretation:
            answer += f"{rs_interpretation}\n"

        # 综合结论
        if conclusion:
            answer += f"\n💡 {conclusion}"

        return answer

    def _format_validation_message(self, result: Dict) -> str:
        """格式化验证信息"""
        details = result.get("details", {})
        message = details.get("message", "")
        consistency = result.get("consistency", "")

        if consistency == "high":
            icon = "✅"
        elif consistency == "medium":
            icon = "⚠️"
        else:
            icon = "❌"

        return f"{icon} 数据验证：{message}"

    def _handle_error_friendly(self, error: Exception, query: str) -> Dict:
        """友好的错误处理"""
        error_type = type(error).__name__

        if "SymbolNotFound" in error_type:
            return self.error_handler.handle_symbol_not_found(query)
        elif "DataUnavailable" in error_type:
            return self.error_handler.handle_data_unavailable("", str(error))
        elif "RateLimit" in error_type:
            return self.error_handler.handle_rate_limit()
        elif "Network" in error_type:
            return self.error_handler.handle_network_error()
        else:
            # 尝试降级
            return self.degradation.degrade_gracefully(query, "unknown_error")
