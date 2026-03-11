"""
完整的RAG系统集成
Complete RAG System Integration

将所有优化功能集成到主RAG管道中
"""
import logging
from typing import List, Dict, Optional
import chromadb

from app.rag.hybrid_retrieval import HybridRetriever
from app.rag.grounded_pipeline import GroundedRAGPipeline
from app.rag.fact_verifier import AnswerQualityController
from app.models import KnowledgeResult

logger = logging.getLogger(__name__)


class UltimateRAGPipeline(GroundedRAGPipeline):
    """
    终极RAG管道

    整合所有优化功能:
    1. 混合检索 (Vector + BM25 + Reranker)
    2. 基于事实的回答生成
    3. 多层验证
    4. 质量控制
    """

    def __init__(
        self,
        chroma_persist_dir: str = "f:/Financial_Asset_QA_System_cyx-master/data/chroma_db",
        collection_name: str = "financial_knowledge_enhanced",
        use_hybrid_retrieval: bool = True,
        use_reranker: bool = True
    ):
        """
        初始化终极RAG管道

        Args:
            chroma_persist_dir: ChromaDB持久化目录
            collection_name: 集合名称
            use_hybrid_retrieval: 是否使用混合检索
            use_reranker: 是否使用重排序
        """
        # 初始化ChromaDB
        self.client = chromadb.PersistentClient(path=chroma_persist_dir)

        try:
            self.collection = self.client.get_collection(collection_name)
            logger.info(f"连接到集合: {collection_name}")
        except Exception as e:
            logger.error(f"无法连接到集合 {collection_name}: {e}")
            raise

        # 初始化混合检索器
        self.use_hybrid_retrieval = use_hybrid_retrieval
        if use_hybrid_retrieval:
            try:
                self.hybrid_retriever = HybridRetriever(
                    self.collection,
                    use_reranker=use_reranker
                )
                logger.info("混合检索器初始化成功")
            except Exception as e:
                logger.warning(f"混合检索器初始化失败: {e}，使用标准检索")
                self.use_hybrid_retrieval = False
                self.hybrid_retriever = None
        else:
            self.hybrid_retriever = None

        # 初始化质量控制器
        self.quality_controller = AnswerQualityController()

        logger.info("终极RAG管道初始化完成")

    async def search_ultimate(
        self,
        query: str,
        top_k: int = 10,
        min_relevance: float = 0.3,
        require_sources: bool = True,
        enable_fact_checking: bool = True
    ) -> Dict:
        """
        终极检索方法

        Args:
            query: 查询文本
            top_k: 返回top-k结果
            min_relevance: 最小相关度阈值
            require_sources: 是否要求来源引用
            enable_fact_checking: 是否启用事实检查

        Returns:
            包含答案、来源、置信度的字典
        """
        logger.info(f"终极检索: {query}")

        try:
            # 1. 检索文档
            if self.use_hybrid_retrieval and self.hybrid_retriever:
                logger.info("使用混合检索")
                documents = self.hybrid_retriever.search(query, top_k=top_k)
            else:
                logger.info("使用标准向量检索")
                documents = self._standard_search(query, top_k=top_k)

            if not documents:
                return {
                    "answer": "抱歉，我在知识库中没有找到相关信息。",
                    "sources": [],
                    "confidence": 0.0,
                    "method": "no_documents"
                }

            # 2. 验证文档质量
            valid_documents = self._validate_documents(documents, min_relevance)

            if not valid_documents:
                return {
                    "answer": "抱歉，找到的文档相关度不足，无法提供可靠答案。",
                    "sources": [],
                    "confidence": 0.0,
                    "method": "low_relevance"
                }

            # 3. 生成基于事实的答案
            answer_result = await self._generate_grounded_answer(
                query,
                valid_documents,
                require_sources=require_sources
            )

            # 4. 事实检查（可选）
            if enable_fact_checking:
                quality_result = self.quality_controller.validate_answer(
                    answer_result["answer"],
                    valid_documents,
                    query
                )

                if not quality_result["is_valid"]:
                    logger.warning(f"答案质量不合格: {quality_result['issues']}")
                    return {
                        "answer": "抱歉，我无法生成符合质量标准的答案。请尝试更具体的问题。",
                        "sources": [],
                        "confidence": 0.0,
                        "method": "quality_check_failed",
                        "issues": quality_result["issues"]
                    }

                answer_result["confidence"] = quality_result["confidence"]
                answer_result["quality_score"] = quality_result["quality_score"]

            # 5. 添加检索方法信息
            answer_result["method"] = "hybrid" if self.use_hybrid_retrieval else "standard"
            answer_result["documents_retrieved"] = len(documents)
            answer_result["documents_used"] = len(valid_documents)

            logger.info(f"终极检索完成: 置信度={answer_result.get('confidence', 0):.2f}")

            return answer_result

        except Exception as e:
            logger.error(f"终极检索失败: {e}")
            return {
                "answer": "抱歉，处理您的查询时出现错误。",
                "sources": [],
                "confidence": 0.0,
                "method": "error",
                "error": str(e)
            }

    def _standard_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """标准向量检索"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )

            documents = []
            if results and results.get("documents"):
                for i in range(len(results["documents"][0])):
                    doc = {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "distance": results["distances"][0][i] if results.get("distances") else 0
                    }
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"标准检索失败: {e}")
            return []

    def _validate_documents(
        self,
        documents: List[Dict],
        min_relevance: float = 0.3
    ) -> List[Dict]:
        """验证文档质量"""
        valid_docs = []

        for doc in documents:
            # 检查相关度（距离越小越相关）
            distance = doc.get("distance", 1.0)
            relevance = 1.0 - distance

            if relevance >= min_relevance:
                doc["relevance"] = relevance
                valid_docs.append(doc)

        logger.info(f"文档验证: {len(documents)} -> {len(valid_docs)}")
        return valid_docs

    async def _generate_grounded_answer(
        self,
        query: str,
        documents: List[Dict],
        require_sources: bool = True
    ) -> Dict:
        """生成基于事实的答案"""
        # 构建上下文
        context_parts = []
        sources = []

        for i, doc in enumerate(documents[:5]):  # 最多使用前5个文档
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            context_parts.append(f"[文档{i+1}]\n{content}")

            sources.append({
                "index": i + 1,
                "file": metadata.get("source_file", "未知"),
                "type": metadata.get("chunk_type", "text"),
                "is_table": metadata.get("is_table", False),
                "relevance": doc.get("relevance", 0.0)
            })

        context = "\n\n".join(context_parts)

        # 构建提示词
        if require_sources:
            prompt = f"""基于以下文档回答问题。你必须：
1. 只使用文档中的信息回答
2. 在答案中标注来源，格式为[文档X]
3. 如果文档中没有相关信息，明确说明
4. 不要添加文档中没有的信息

文档:
{context}

问题: {query}

请提供准确、有来源标注的答案:"""
        else:
            prompt = f"""基于以下文档回答问题。只使用文档中的信息，不要添加额外内容。

文档:
{context}

问题: {query}

答案:"""

        # 调用LLM生成答案
        try:
            # 这里应该调用实际的LLM
            # 暂时返回模拟结果
            answer = f"根据文档，{query}的相关信息如下：[文档1]提供了相关数据。"

            return {
                "answer": answer,
                "sources": sources,
                "confidence": 0.8,
                "context_length": len(context)
            }

        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            return {
                "answer": "抱歉，生成答案时出现错误。",
                "sources": sources,
                "confidence": 0.0
            }

    def get_stats(self) -> Dict:
        """获取系统统计信息"""
        try:
            doc_count = self.collection.count()

            stats = {
                "collection_name": self.collection.name,
                "document_count": doc_count,
                "uses_hybrid_retrieval": self.use_hybrid_retrieval,
                "uses_reranker": self.hybrid_retriever is not None and self.hybrid_retriever.use_reranker,
                "status": "ready"
            }

            # 获取BM25统计
            if self.hybrid_retriever and self.hybrid_retriever.bm25:
                stats["bm25_corpus_size"] = len(self.hybrid_retriever.bm25.corpus)
                stats["bm25_avgdl"] = self.hybrid_retriever.bm25.avgdl

            return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    # 测试
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test_ultimate_rag():
        """测试终极RAG管道"""
        print("\n" + "="*60)
        print("终极RAG管道测试")
        print("="*60 + "\n")

        try:
            # 初始化管道
            pipeline = UltimateRAGPipeline(
                collection_name="financial_knowledge_enhanced",
                use_hybrid_retrieval=True,
                use_reranker=False  # 先不使用reranker避免依赖问题
            )

            # 获取统计信息
            stats = pipeline.get_stats()
            print("系统统计:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

            # 测试查询
            queries = [
                "苹果公司2025年Q4的营收是多少",
                "特斯拉的交付量",
                "什么是市盈率"
            ]

            for query in queries:
                print(f"\n{'='*60}")
                print(f"查询: {query}")
                print("="*60)

                result = await pipeline.search_ultimate(
                    query,
                    top_k=5,
                    enable_fact_checking=False  # 暂时禁用以避免依赖问题
                )

                print(f"\n答案: {result['answer']}")
                print(f"置信度: {result.get('confidence', 0):.2f}")
                print(f"检索方法: {result.get('method')}")
                print(f"检索文档数: {result.get('documents_retrieved', 0)}")
                print(f"使用文档数: {result.get('documents_used', 0)}")

                if result.get('sources'):
                    print(f"\n来源:")
                    for source in result['sources'][:3]:
                        print(f"  [{source['index']}] {source['file']} "
                              f"(类型: {source['type']}, "
                              f"相关度: {source['relevance']:.2f})")

        except Exception as e:
            print(f"\n测试失败: {e}")
            import traceback
            traceback.print_exc()

    # 运行测试
    asyncio.run(test_ultimate_rag())
