"""
增强的 RAG 管道 - 整合所有优化功能
Enhanced RAG Pipeline - Integrate All Optimizations

整合：
1. 查询改写 (HyDE + Multi-Query)
2. 混合检索 (Lexical + BM25 + Vector)
3. 重排序 (优化权重)
4. 可观测性 (链路追踪)
5. 事实验证 (幻觉检测)
"""
import logging
from typing import Dict, List, Optional, Any
import time

from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.rag.query_rewriter import QueryRewriterPipeline
from app.rag.observability import RAGObserver, get_global_observer
from app.rag.fact_verifier import AnswerQualityController
from app.models import KnowledgeResult, Document
from app.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class EnhancedRAGPipeline(HybridRAGPipeline):
    """
    增强的 RAG 管道

    集成所有优化功能：
    - 查询改写提升召回
    - 混合检索提升精度
    - 重排序优化排序
    - 可观测性监控性能
    - 事实验证保证质量
    """

    def __init__(
        self,
        enable_query_rewriting: bool = True,
        enable_observability: bool = True,
        enable_quality_control: bool = True,
        observer: Optional[RAGObserver] = None
    ):
        """
        初始化增强 RAG 管道

        Args:
            enable_query_rewriting: 是否启用查询改写
            enable_observability: 是否启用可观测性
            enable_quality_control: 是否启用质量控制
            observer: 自定义观察器（可选）
        """
        super().__init__()

        # 查询改写器
        self.enable_query_rewriting = enable_query_rewriting
        if enable_query_rewriting:
            try:
                self.query_rewriter = QueryRewriterPipeline()
                logger.info("查询改写器初始化成功")
            except Exception as e:
                logger.warning(f"查询改写器初始化失败: {e}")
                self.enable_query_rewriting = False
                self.query_rewriter = None
        else:
            self.query_rewriter = None

        # 可观测性
        self.enable_observability = enable_observability
        if enable_observability:
            self.observer = observer or get_global_observer()
            logger.info("可观测性系统已启用")
        else:
            self.observer = None

        # 质量控制
        self.enable_quality_control = enable_quality_control
        if enable_quality_control:
            self.quality_controller = AnswerQualityController()
            logger.info("质量控制系统已启用")
        else:
            self.quality_controller = None

        # LLM 客户端（用于生成答案）
        self.llm_client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL

        logger.info("增强 RAG 管道初始化完成")

    async def search_enhanced(
        self,
        query: str,
        use_query_rewriting: Optional[bool] = None,
        rewrite_strategy: Optional[str] = None,
        use_hybrid: bool = True,
        generate_answer: bool = False,
        **kwargs
    ) -> Dict:
        """
        增强检索

        Args:
            query: 用户查询
            use_query_rewriting: 是否使用查询改写（None=使用配置）
            rewrite_strategy: 改写策略 ("hyde", "multi_query", "both")
            use_hybrid: 是否使用混合检索
            generate_answer: 是否生成答案
            **kwargs: 其他参数

        Returns:
            增强检索结果
        """
        # 开始追踪
        trace_id = None
        if self.enable_observability and self.observer:
            trace_id = self.observer.start_trace(query)

        try:
            # 阶段 1: 查询改写
            queries_to_search = [query]
            rewrite_result = None

            if use_query_rewriting is None:
                use_query_rewriting = self.enable_query_rewriting and settings.RAG_USE_QUERY_REWRITING

            if use_query_rewriting and self.query_rewriter:
                start_time = time.time()

                strategy = rewrite_strategy or settings.RAG_QUERY_REWRITE_STRATEGY
                rewrite_result = await self.query_rewriter.rewrite(
                    query,
                    strategy=strategy,
                    num_queries=settings.RAG_MULTI_QUERY_NUM
                )

                queries_to_search = rewrite_result["rewritten_queries"]
                duration_ms = (time.time() - start_time) * 1000

                if self.observer and trace_id:
                    self.observer.record_stage(
                        trace_id=trace_id,
                        stage_name="query_rewriting",
                        documents_retrieved=len(queries_to_search),
                        top_score=1.0,
                        avg_score=1.0,
                        duration_ms=duration_ms,
                        metadata={"strategy": strategy}
                    )

                logger.info(f"查询改写: {query} -> {len(queries_to_search)} 个查询")

            # 阶段 2: 混合检索（对每个改写的查询）
            all_results = []
            retrieval_start = time.time()

            for q in queries_to_search:
                result = await super().search(q, use_hybrid=use_hybrid, **kwargs)
                all_results.append(result)

            # 合并结果（去重）
            merged_result = self._merge_search_results(all_results)
            retrieval_duration = (time.time() - retrieval_start) * 1000

            if self.observer and trace_id:
                docs = merged_result.documents
                self.observer.record_stage(
                    trace_id=trace_id,
                    stage_name="retrieval",
                    documents_retrieved=len(docs),
                    top_score=docs[0].score if docs else 0.0,
                    avg_score=sum(d.score for d in docs) / len(docs) if docs else 0.0,
                    duration_ms=retrieval_duration,
                    metadata={
                        "strategy": merged_result.retrieval_meta.get("strategy", "unknown"),
                        "queries_searched": len(queries_to_search)
                    }
                )

            # 阶段 3: 生成答案（可选）
            answer = None
            answer_metadata = {}

            if generate_answer and merged_result.documents:
                gen_start = time.time()
                answer_result = await self._generate_answer(query, merged_result.documents)
                gen_duration = (time.time() - gen_start) * 1000

                answer = answer_result["answer"]
                answer_metadata = answer_result.get("metadata", {})

                if self.observer and trace_id:
                    self.observer.record_stage(
                        trace_id=trace_id,
                        stage_name="generation",
                        documents_retrieved=0,
                        top_score=1.0,
                        avg_score=1.0,
                        duration_ms=gen_duration,
                        metadata={"answer_length": len(answer)}
                    )

                # 阶段 4: 质量控制（可选）
                if self.enable_quality_control and self.quality_controller:
                    qc_start = time.time()

                    source_docs = [
                        {"id": i+1, "content": doc.content}
                        for i, doc in enumerate(merged_result.documents[:5])
                    ]

                    qc_result = self.quality_controller.check_and_control(
                        answer=answer,
                        source_documents=source_docs,
                        query=query,
                        min_confidence=0.7
                    )

                    qc_duration = (time.time() - qc_start) * 1000

                    if self.observer and trace_id:
                        self.observer.record_stage(
                            trace_id=trace_id,
                            stage_name="quality_control",
                            documents_retrieved=0,
                            top_score=qc_result["original_confidence"],
                            avg_score=qc_result["original_confidence"],
                            duration_ms=qc_duration,
                            metadata={
                                "passed": qc_result["passed_quality_check"],
                                "fallback_used": qc_result["fallback_used"]
                            }
                        )

                    # 使用质量控制后的答案
                    answer = qc_result["answer"]
                    answer_metadata["quality_check"] = qc_result

            # 结束追踪
            if self.observer and trace_id:
                self.observer.end_trace(
                    trace_id=trace_id,
                    final_documents_count=len(merged_result.documents),
                    final_answer_length=len(answer) if answer else 0,
                    success=True,
                    metadata={
                        "query_rewriting_used": use_query_rewriting,
                        "answer_generated": generate_answer
                    }
                )

            # 构建返回结果
            result = {
                "query": query,
                "trace_id": trace_id,
                "documents": merged_result.documents,
                "total_found": merged_result.total_found,
                "retrieval_meta": merged_result.retrieval_meta,
                "answer": answer,
                "answer_metadata": answer_metadata,
                "rewrite_result": rewrite_result
            }

            return result

        except Exception as e:
            logger.error(f"增强检索失败: {e}", exc_info=True)

            # 记录失败
            if self.observer and trace_id:
                self.observer.end_trace(
                    trace_id=trace_id,
                    success=False,
                    error=str(e)
                )

            raise

    def _merge_search_results(self, results: List[KnowledgeResult]) -> KnowledgeResult:
        """
        合并多个检索结果（去重）

        Args:
            results: 检索结果列表

        Returns:
            合并后的结果
        """
        if not results:
            return KnowledgeResult(documents=[], total_found=0, query="")

        if len(results) == 1:
            return results[0]

        # 使用 chunk_id 去重
        seen_chunks = set()
        merged_docs = []

        for result in results:
            for doc in result.documents:
                chunk_id = doc.chunk_id or doc.content[:100]

                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    merged_docs.append(doc)

        # 按分数排序
        merged_docs.sort(key=lambda d: d.score, reverse=True)

        # 限制数量
        merged_docs = merged_docs[:settings.RAG_TOP_N * 2]

        return KnowledgeResult(
            documents=merged_docs,
            total_found=len(merged_docs),
            query=results[0].query,
            retrieval_meta={"strategy": "merged_multi_query"}
        )

    async def _generate_answer(
        self,
        query: str,
        documents: List[Document]
    ) -> Dict:
        """
        生成答案

        Args:
            query: 查询
            documents: 检索到的文档

        Returns:
            答案结果
        """
        # 构建上下文
        context_parts = []
        for i, doc in enumerate(documents[:5], 1):
            context_parts.append(f"[文档{i}]\n{doc.content}\n")

        context = "\n".join(context_parts)

        # 构建 prompt
        prompt = f"""基于以下文档回答问题。要求：
1. 只使用文档中的信息
2. 标注来源 [文档X]
3. 简洁明了

文档：
{context}

问题：{query}

答案："""

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个严谨的金融知识助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=600
            )

            answer = response.choices[0].message.content.strip()

            return {
                "answer": answer,
                "metadata": {
                    "documents_used": len(documents[:5]),
                    "context_length": len(context)
                }
            }

        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            # 降级：返回最相关文档
            return {
                "answer": f"根据相关资料：\n\n{documents[0].content}",
                "metadata": {
                    "fallback": True,
                    "error": str(e)
                }
            }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = super().get_status()

        if self.observer:
            stats["observability"] = self.observer.get_summary()

        if self.quality_controller:
            stats["quality_control"] = self.quality_controller.get_quality_report()

        stats["features"] = {
            "query_rewriting": self.enable_query_rewriting,
            "observability": self.enable_observability,
            "quality_control": self.enable_quality_control
        }

        return stats


if __name__ == "__main__":
    # 测试
    import asyncio

    logging.basicConfig(level=logging.INFO)

    async def test_enhanced_pipeline():
        """测试增强 RAG 管道"""
        print("\n" + "="*60)
        print("增强 RAG 管道测试")
        print("="*60 + "\n")

        try:
            # 初始化管道
            pipeline = EnhancedRAGPipeline(
                enable_query_rewriting=True,
                enable_observability=True,
                enable_quality_control=True
            )

            # 测试查询
            query = "什么是市盈率？"

            print(f"查询: {query}\n")

            # 执行增强检索
            result = await pipeline.search_enhanced(
                query=query,
                use_query_rewriting=True,
                rewrite_strategy="multi_query",
                generate_answer=True
            )

            print(f"追踪ID: {result['trace_id']}")
            print(f"检索到文档数: {len(result['documents'])}")

            if result['documents']:
                print(f"\nTop 3 文档:")
                for i, doc in enumerate(result['documents'][:3], 1):
                    print(f"  {i}. [{doc.source}] 分数: {doc.score:.3f}")
                    print(f"     {doc.content[:100]}...")

            if result['answer']:
                print(f"\n答案:\n{result['answer']}")

            # 打印统计
            print("\n" + "="*60)
            stats = pipeline.get_stats()
            print("系统统计:")
            print(f"  文档数: {stats['chunks']}")
            print(f"  BM25就绪: {stats['bm25_ready']}")
            print(f"  Embedding就绪: {stats['embedding_model_ready']}")

            if 'observability' in stats:
                obs = stats['observability']
                print(f"\n可观测性:")
                print(f"  总追踪数: {obs['total_traces']}")
                print(f"  成功率: {obs['success_rate']:.2%}")
                print(f"  平均耗时: {obs['avg_total_duration_ms']:.2f}ms")

        except Exception as e:
            print(f"\n测试失败: {e}")
            import traceback
            traceback.print_exc()

    # 运行测试
    asyncio.run(test_enhanced_pipeline())
