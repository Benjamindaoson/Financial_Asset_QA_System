"""
基于事实的RAG管道 - 消除幻觉，保证答案质量
Grounded RAG Pipeline - Eliminate Hallucinations, Guarantee Answer Quality
"""
from typing import Dict, List, Optional, Tuple
import logging
from openai import AsyncOpenAI

from app.rag.enhanced_pipeline import EnhancedRAGPipeline
from app.models import KnowledgeResult
from app.config import settings

logger = logging.getLogger(__name__)


class GroundedRAGPipeline(EnhancedRAGPipeline):
    """
    基于事实的RAG管道

    核心原则：
    1. 必须基于检索到的文档回答
    2. 不允许LLM自由发挥
    3. 如果文档不足，明确告知用户
    4. 提供引用来源
    """

    # 最低文档相关性阈值
    MIN_RELEVANCE_SCORE = 0.3

    # 最少需要的文档数量
    MIN_DOCUMENTS_REQUIRED = 1

    def __init__(self):
        """初始化 Grounded RAG Pipeline"""
        super().__init__()
        # 初始化 LLM 客户端
        self.llm_client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL

    async def search_grounded(
        self,
        query: str,
        min_relevance: float = None,
        require_sources: bool = True,
    ) -> Dict:
        """
        基于事实的搜索

        Args:
            query: 用户查询
            min_relevance: 最低相关性阈值
            require_sources: 是否要求提供来源

        Returns:
            包含答案、来源和置信度的字典
        """
        min_relevance = min_relevance or self.MIN_RELEVANCE_SCORE

        # 1. 检索文档
        logger.info(f"检索查询: {query}")
        rag_result = await self.search(query, use_hybrid=True)

        # 2. 验证文档质量
        validation_result = self._validate_documents(
            rag_result,
            min_relevance=min_relevance
        )

        if not validation_result["is_valid"]:
            # 文档不足，返回明确的"不知道"
            return self._handle_insufficient_documents(
                query,
                validation_result["reason"]
            )

        # 3. 提取相关文档
        relevant_docs = validation_result["relevant_docs"]

        # 4. 生成基于事实的答案
        grounded_answer = await self._generate_grounded_answer(
            query,
            relevant_docs,
            require_sources=require_sources
        )

        # 5. 验证答案质量
        answer_validation = self._validate_answer(
            grounded_answer,
            relevant_docs
        )

        if not answer_validation["is_valid"]:
            # 答案质量不足
            return self._handle_low_quality_answer(
                query,
                relevant_docs,
                answer_validation["reason"]
            )

        return {
            "answer": grounded_answer["text"],
            "sources": grounded_answer["sources"],
            "confidence": answer_validation["confidence"],
            "document_count": len(relevant_docs),
            "grounded": True,
            "validation": {
                "documents_valid": True,
                "answer_valid": True,
                "has_sources": len(grounded_answer["sources"]) > 0
            }
        }

    def _validate_documents(
        self,
        rag_result: KnowledgeResult,
        min_relevance: float
    ) -> Dict:
        """
        验证检索到的文档是否足够回答问题

        Args:
            rag_result: RAG检索结果
            min_relevance: 最低相关性阈值

        Returns:
            验证结果
        """
        documents = rag_result.documents

        if not documents:
            return {
                "is_valid": False,
                "reason": "no_documents",
                "message": "未找到相关文档"
            }

        # 过滤低相关性文档
        relevant_docs = [
            doc for doc in documents
            if doc.score >= min_relevance
        ]

        if len(relevant_docs) < self.MIN_DOCUMENTS_REQUIRED:
            return {
                "is_valid": False,
                "reason": "low_relevance",
                "message": f"找到 {len(documents)} 个文档，但相关性不足（阈值: {min_relevance}）",
                "best_score": max([doc.score for doc in documents]) if documents else 0
            }

        return {
            "is_valid": True,
            "relevant_docs": relevant_docs,
            "total_docs": len(documents),
            "relevant_count": len(relevant_docs)
        }

    async def _generate_grounded_answer(
        self,
        query: str,
        relevant_docs: List,
        require_sources: bool = True
    ) -> Dict:
        """
        生成基于事实的答案

        Args:
            query: 用户查询
            relevant_docs: 相关文档列表
            require_sources: 是否要求提供来源

        Returns:
            包含答案文本和来源的字典
        """
        # 构建上下文
        context_parts = []
        sources = []

        for i, doc in enumerate(relevant_docs[:5], 1):  # 最多使用前5个文档
            context_parts.append(f"[文档{i}]\n{doc.content}\n")
            sources.append({
                "id": i,
                "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "metadata": doc.metadata,
                "score": doc.score
            })

        context = "\n".join(context_parts)

        # 构建严格的提示词
        prompt = self._build_grounded_prompt(query, context, require_sources)

        # 调用LLM
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个严谨的金融知识助手，只基于提供的文档回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            answer_text = response.choices[0].message.content.strip()

            # 验证答案是否包含来源引用
            if require_sources and not self._has_source_citations(answer_text):
                # 如果没有引用，添加来源信息
                answer_text = self._add_source_citations(answer_text, sources)

            return {
                "text": answer_text,
                "sources": sources,
                "context_used": context
            }

        except Exception as e:
            logger.error(f"LLM生成失败: {e}")
            # LLM失败时，使用文档直接回答
            return self._fallback_answer(query, relevant_docs, sources)

    def _build_grounded_prompt(
        self,
        query: str,
        context: str,
        require_sources: bool
    ) -> str:
        """
        构建严格的提示词，防止幻觉

        Args:
            query: 用户查询
            context: 上下文文档
            require_sources: 是否要求引用来源

        Returns:
            提示词
        """
        prompt = f"""你是一个严谨的金融知识助手。请严格遵守以下规则：

【核心规则】
1. 只能基于提供的文档回答问题
2. 不允许使用文档之外的知识
3. 如果文档中没有相关信息，必须明确说"根据现有资料无法回答"
4. 必须引用来源，使用 [文档X] 标注

【提供的文档】
{context}

【用户问题】
{query}

【回答要求】
1. 直接回答问题，简洁明了
2. 每个关键信息后标注来源，如：市盈率是股价除以每股收益[文档1]
3. 如果多个文档有相同信息，引用最相关的
4. 不要添加文档中没有的信息
5. 不要做推测或假设

请回答："""

        return prompt

    def _has_source_citations(self, text: str) -> bool:
        """检查答案是否包含来源引用"""
        import re
        # 检查是否有 [文档X] 格式的引用
        pattern = r'\[文档\d+\]'
        return bool(re.search(pattern, text))

    def _add_source_citations(self, text: str, sources: List[Dict]) -> str:
        """为答案添加来源引用"""
        if not sources:
            return text

        # 在答案末尾添加来源列表
        citations = "\n\n【参考来源】\n"
        for source in sources:
            citations += f"[文档{source['id']}] {source['content'][:100]}...\n"

        return text + citations

    def _fallback_answer(
        self,
        query: str,
        relevant_docs: List,
        sources: List[Dict]
    ) -> Dict:
        """
        LLM失败时的降级回答
        直接使用最相关的文档内容
        """
        # 使用最相关的文档
        best_doc = relevant_docs[0]

        answer_text = f"""根据相关资料：

{best_doc.content}

【参考来源】
[文档1] {best_doc.content[:200]}...
"""

        return {
            "text": answer_text,
            "sources": sources,
            "context_used": best_doc.content,
            "fallback": True
        }

    def _validate_answer(
        self,
        grounded_answer: Dict,
        relevant_docs: List
    ) -> Dict:
        """
        验证答案质量

        Args:
            grounded_answer: 生成的答案
            relevant_docs: 相关文档

        Returns:
            验证结果
        """
        answer_text = grounded_answer["text"]
        sources = grounded_answer["sources"]

        # 检查1: 答案长度
        if len(answer_text.strip()) < 10:
            return {
                "is_valid": False,
                "reason": "answer_too_short",
                "confidence": 0.0
            }

        # 检查2: 是否包含来源引用
        has_citations = self._has_source_citations(answer_text)

        # 检查3: 答案是否与文档相关
        relevance_score = self._calculate_answer_relevance(
            answer_text,
            relevant_docs
        )

        # 检查4: 是否包含"不知道"等拒绝回答的词
        refusal_keywords = ["不知道", "无法回答", "没有相关信息", "无法确定"]
        is_refusal = any(kw in answer_text for kw in refusal_keywords)

        if is_refusal:
            return {
                "is_valid": False,
                "reason": "refusal_answer",
                "confidence": 0.0
            }

        # 计算置信度
        confidence = self._calculate_answer_confidence(
            has_citations=has_citations,
            relevance_score=relevance_score,
            source_count=len(sources)
        )

        return {
            "is_valid": True,
            "confidence": confidence,
            "has_citations": has_citations,
            "relevance_score": relevance_score
        }

    def _calculate_answer_relevance(
        self,
        answer_text: str,
        relevant_docs: List
    ) -> float:
        """
        计算答案与文档的相关性
        简单实现：检查答案中有多少词出现在文档中
        """
        answer_words = set(answer_text.lower().split())
        doc_words = set()

        for doc in relevant_docs:
            doc_words.update(doc.content.lower().split())

        if not answer_words:
            return 0.0

        # 计算重叠率
        overlap = len(answer_words & doc_words)
        relevance = overlap / len(answer_words)

        return min(relevance, 1.0)

    def _calculate_answer_confidence(
        self,
        has_citations: bool,
        relevance_score: float,
        source_count: int
    ) -> float:
        """
        计算答案置信度

        Args:
            has_citations: 是否有引用
            relevance_score: 相关性分数
            source_count: 来源数量

        Returns:
            置信度 (0-1)
        """
        confidence = 0.0

        # 有引用 +0.3
        if has_citations:
            confidence += 0.3

        # 相关性分数 +0.4
        confidence += relevance_score * 0.4

        # 来源数量 +0.3
        source_factor = min(source_count / 3, 1.0)  # 3个来源为满分
        confidence += source_factor * 0.3

        return min(confidence, 1.0)

    def _handle_insufficient_documents(
        self,
        query: str,
        reason: str
    ) -> Dict:
        """
        处理文档不足的情况
        明确告知用户无法回答
        """
        if reason == "no_documents":
            message = "抱歉，我在知识库中没有找到与您问题相关的信息。"
        elif reason == "low_relevance":
            message = "抱歉，虽然找到了一些文档，但与您的问题相关性较低，无法给出准确答案。"
        else:
            message = "抱歉，当前无法回答您的问题。"

        suggestions = self._generate_search_suggestions(query)

        return {
            "answer": message,
            "sources": [],
            "confidence": 0.0,
            "grounded": True,
            "can_answer": False,
            "reason": reason,
            "suggestions": suggestions
        }

    def _handle_low_quality_answer(
        self,
        query: str,
        relevant_docs: List,
        reason: str
    ) -> Dict:
        """
        处理低质量答案
        提供文档摘要而非生成答案
        """
        # 直接返回最相关的文档内容
        best_doc = relevant_docs[0]

        answer = f"""根据相关资料，我找到了以下信息：

{best_doc.content}

【说明】由于答案质量验证未通过（原因：{reason}），我直接提供了最相关的文档内容供您参考。"""

        return {
            "answer": answer,
            "sources": [{
                "id": 1,
                "content": best_doc.content,
                "metadata": best_doc.metadata,
                "score": best_doc.score
            }],
            "confidence": 0.5,
            "grounded": True,
            "quality_warning": True,
            "reason": reason
        }

    def _generate_search_suggestions(self, query: str) -> List[str]:
        """
        生成搜索建议

        Args:
            query: 原始查询

        Returns:
            建议列表
        """
        suggestions = [
            "尝试使用更具体的金融术语",
            "检查是否有拼写错误",
            "尝试换一种问法"
        ]

        # 根据查询类型添加具体建议
        if "是什么" in query or "什么是" in query:
            suggestions.append("尝试搜索：市盈率、市净率、ROE等具体指标")
        elif "如何" in query or "怎么" in query:
            suggestions.append("尝试搜索：如何计算市盈率、如何分析财务报表")

        return suggestions
