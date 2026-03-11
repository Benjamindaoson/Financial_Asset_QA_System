"""
查询改写模块 - HyDE 和 Multi-Query
Query Rewriting Module - HyDE and Multi-Query

实现查询改写技术以提升检索质量
"""
import logging
from typing import List, Dict, Optional
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class HyDERewriter:
    """
    HyDE (Hypothetical Document Embeddings) 查询改写器

    核心思想：生成假设性文档来改善检索
    - 让 LLM 生成一个"假设的答案文档"
    - 用这个假设文档做向量检索
    - 比直接用问题检索效果更好
    """

    def __init__(self, llm_client: Optional[AsyncOpenAI] = None):
        """
        初始化 HyDE 改写器

        Args:
            llm_client: LLM 客户端（可选）
        """
        self.llm_client = llm_client or AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL

    async def generate_hypothetical_document(
        self,
        query: str,
        domain: str = "金融"
    ) -> str:
        """
        生成假设性文档

        Args:
            query: 用户查询
            domain: 领域（用于定制 prompt）

        Returns:
            假设性文档
        """
        prompt = self._build_hyde_prompt(query, domain)

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个金融知识专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )

            hypothetical_doc = response.choices[0].message.content.strip()
            logger.info(f"HyDE 生成假设文档: {hypothetical_doc[:100]}...")

            return hypothetical_doc

        except Exception as e:
            logger.error(f"HyDE 生成失败: {e}")
            # 降级：返回原始查询
            return query

    def _build_hyde_prompt(self, query: str, domain: str) -> str:
        """
        构建 HyDE prompt

        Args:
            query: 用户查询
            domain: 领域

        Returns:
            Prompt
        """
        prompt = f"""请根据以下问题，生成一段假设性的答案文档。这段文档应该：
1. 直接回答问题
2. 包含相关的专业术语和概念
3. 简洁明了（200字以内）
4. 不要说"根据..."、"假设..."等前缀，直接给出答案内容

问题：{query}

假设性答案文档："""

        return prompt


class MultiQueryRewriter:
    """
    Multi-Query 查询改写器

    核心思想：从多个角度改写查询
    - 生成 3-5 个不同角度的查询
    - 分别检索后合并结果
    - 提高召回率
    """

    def __init__(self, llm_client: Optional[AsyncOpenAI] = None):
        """
        初始化 Multi-Query 改写器

        Args:
            llm_client: LLM 客户端（可选）
        """
        self.llm_client = llm_client or AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL

    async def generate_multi_queries(
        self,
        query: str,
        num_queries: int = 3
    ) -> List[str]:
        """
        生成多角度查询

        Args:
            query: 原始查询
            num_queries: 生成查询数量

        Returns:
            查询列表（包含原始查询）
        """
        prompt = self._build_multi_query_prompt(query, num_queries)

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个查询改写专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=200
            )

            content = response.choices[0].message.content.strip()

            # 解析生成的查询
            queries = self._parse_queries(content)

            # 确保包含原始查询
            if query not in queries:
                queries.insert(0, query)

            logger.info(f"Multi-Query 生成 {len(queries)} 个查询: {queries}")

            return queries[:num_queries + 1]  # 最多返回 num_queries + 原始查询

        except Exception as e:
            logger.error(f"Multi-Query 生成失败: {e}")
            # 降级：返回原始查询
            return [query]

    def _build_multi_query_prompt(self, query: str, num_queries: int) -> str:
        """
        构建 Multi-Query prompt

        Args:
            query: 原始查询
            num_queries: 生成数量

        Returns:
            Prompt
        """
        prompt = f"""请将以下问题改写为 {num_queries} 个不同角度的查询，以便更全面地检索相关信息。

要求：
1. 每个查询从不同角度提问
2. 保持核心意图不变
3. 使用不同的关键词和表达方式
4. 每行一个查询，用数字编号

原始问题：{query}

改写后的查询：
1."""

        return prompt

    def _parse_queries(self, content: str) -> List[str]:
        """
        解析生成的查询列表

        Args:
            content: LLM 生成的内容

        Returns:
            查询列表
        """
        queries = []

        # 按行分割
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()

            # 跳过空行
            if not line:
                continue

            # 移除编号（1. 2. 等）
            import re
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)

            # 移除引号
            cleaned = cleaned.strip('"\'')

            if cleaned and len(cleaned) > 3:
                queries.append(cleaned)

        return queries


class QueryRewriterPipeline:
    """
    查询改写管道

    整合 HyDE 和 Multi-Query
    """

    def __init__(self, llm_client: Optional[AsyncOpenAI] = None):
        """
        初始化查询改写管道

        Args:
            llm_client: LLM 客户端（可选）
        """
        self.hyde = HyDERewriter(llm_client)
        self.multi_query = MultiQueryRewriter(llm_client)

    async def rewrite(
        self,
        query: str,
        strategy: str = "multi_query",
        **kwargs
    ) -> Dict:
        """
        改写查询

        Args:
            query: 原始查询
            strategy: 改写策略 ("hyde", "multi_query", "both")
            **kwargs: 额外参数

        Returns:
            改写结果
        """
        result = {
            "original_query": query,
            "strategy": strategy,
            "rewritten_queries": [],
            "hypothetical_doc": None
        }

        if strategy == "hyde":
            # 仅使用 HyDE
            hypothetical_doc = await self.hyde.generate_hypothetical_document(query)
            result["hypothetical_doc"] = hypothetical_doc
            result["rewritten_queries"] = [hypothetical_doc]

        elif strategy == "multi_query":
            # 仅使用 Multi-Query
            queries = await self.multi_query.generate_multi_queries(
                query,
                num_queries=kwargs.get("num_queries", 3)
            )
            result["rewritten_queries"] = queries

        elif strategy == "both":
            # 同时使用两种策略
            hypothetical_doc = await self.hyde.generate_hypothetical_document(query)
            queries = await self.multi_query.generate_multi_queries(
                query,
                num_queries=kwargs.get("num_queries", 2)
            )

            result["hypothetical_doc"] = hypothetical_doc
            result["rewritten_queries"] = [hypothetical_doc] + queries

        else:
            # 未知策略，返回原始查询
            logger.warning(f"未知的改写策略: {strategy}")
            result["rewritten_queries"] = [query]

        logger.info(f"查询改写完成: {strategy}, 生成 {len(result['rewritten_queries'])} 个查询")

        return result


# 便捷函数
async def rewrite_query_hyde(query: str) -> str:
    """
    使用 HyDE 改写查询

    Args:
        query: 原始查询

    Returns:
        假设性文档
    """
    rewriter = HyDERewriter()
    return await rewriter.generate_hypothetical_document(query)


async def rewrite_query_multi(query: str, num_queries: int = 3) -> List[str]:
    """
    使用 Multi-Query 改写查询

    Args:
        query: 原始查询
        num_queries: 生成数量

    Returns:
        查询列表
    """
    rewriter = MultiQueryRewriter()
    return await rewriter.generate_multi_queries(query, num_queries)


if __name__ == "__main__":
    # 测试
    import asyncio

    logging.basicConfig(level=logging.INFO)

    async def test_query_rewriter():
        """测试查询改写"""
        print("\n" + "="*60)
        print("查询改写测试")
        print("="*60 + "\n")

        query = "什么是市盈率？"

        # 测试 HyDE
        print("1. HyDE 测试")
        print("-" * 60)
        hyde_doc = await rewrite_query_hyde(query)
        print(f"原始查询: {query}")
        print(f"假设文档: {hyde_doc}\n")

        # 测试 Multi-Query
        print("2. Multi-Query 测试")
        print("-" * 60)
        multi_queries = await rewrite_query_multi(query, num_queries=3)
        print(f"原始查询: {query}")
        print("改写查询:")
        for i, q in enumerate(multi_queries, 1):
            print(f"  {i}. {q}")
        print()

        # 测试完整管道
        print("3. 完整管道测试")
        print("-" * 60)
        pipeline = QueryRewriterPipeline()
        result = await pipeline.rewrite(query, strategy="both", num_queries=2)
        print(f"策略: {result['strategy']}")
        print(f"假设文档: {result['hypothetical_doc']}")
        print("改写查询:")
        for i, q in enumerate(result['rewritten_queries'], 1):
            print(f"  {i}. {q[:100]}...")

    # 运行测试
    asyncio.run(test_query_rewriter())
