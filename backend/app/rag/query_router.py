"""
查询路由器 - 根据查询类型选择最优策略
Query Router - Select Optimal Strategy Based on Query Type

查询类型：
1. 简单定义查询 - 跳过查询改写，直接检索（节省 800ms）
2. 计算类查询 - 优先检索公式和示例
3. 对比分析查询 - 使用 Multi-Query
4. 复杂推理查询 - 使用完整流程（HyDE + Multi-Query）

预期效果：
- 简单查询延迟: 2000ms → 800ms（节省 60%）
- 总体平均延迟: 2000ms → 1200ms（节省 40%）
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """查询类型"""
    SIMPLE_DEFINITION = "simple_definition"      # 简单定义
    CALCULATION = "calculation"                  # 计算方法
    COMPARISON = "comparison"                    # 对比分析
    COMPLEX_REASONING = "complex_reasoning"      # 复杂推理
    FACTUAL = "factual"                         # 事实查询


@dataclass
class QueryClassification:
    """查询分类结果"""
    query_type: QueryType
    confidence: float
    matched_patterns: List[str]
    recommended_strategy: str
    skip_query_rewriting: bool
    use_hybrid: bool
    top_k: int


class QueryClassifier:
    """
    查询分类器

    使用规则 + 模式匹配快速分类
    """

    # 简单定义查询模式
    SIMPLE_DEFINITION_PATTERNS = [
        r"^什么是.{1,15}[？?]?$",
        r"^.{1,15}是什么[？?]?$",
        r"^.{1,15}的定义[是]?[？?]?$",
        r"^解释.{1,15}[？?]?$",
        r"^.{1,15}指的是[？?]?$",
        r"^.{1,15}含义[？?]?$",
    ]

    # 计算类查询模式
    CALCULATION_PATTERNS = [
        r"如何计算",
        r"怎么计算",
        r"计算公式",
        r"计算方法",
        r"怎么算",
        r"如何求",
        r"公式是",
        r"=.*[+\-*/]",  # 包含数学运算符
    ]

    # 对比分析查询模式
    COMPARISON_PATTERNS = [
        r".+和.+的区别",
        r".+与.+的区别",
        r".+和.+有什么不同",
        r"对比.+和.+",
        r"比较.+和.+",
        r".+还是.+",
        r".+和.+哪个",
    ]

    # 复杂推理查询模式
    COMPLEX_REASONING_PATTERNS = [
        r"为什么",
        r"如何.*才能",
        r"怎样.*才能",
        r"分析.*原因",
        r"影响.*因素",
        r".*的优缺点",
        r".*的利弊",
    ]

    # 金融关键词
    FINANCIAL_KEYWORDS = {
        "指标": ["市盈率", "市净率", "ROE", "ROA", "PE", "PB", "EPS", "净资产收益率"],
        "市场": ["股票", "债券", "基金", "期货", "期权", "证券"],
        "分析": ["财务报表", "资产负债表", "利润表", "现金流量表"],
        "概念": ["金融市场", "资本市场", "货币市场", "风险", "收益"],
    }

    def __init__(self):
        """初始化分类器"""
        self.classification_count = 0

    def classify(self, query: str) -> QueryClassification:
        """
        分类查询

        Args:
            query: 用户查询

        Returns:
            分类结果
        """
        query = query.strip()
        self.classification_count += 1

        # 1. 简单定义查询
        if result := self._check_simple_definition(query):
            return result

        # 2. 计算类查询
        if result := self._check_calculation(query):
            return result

        # 3. 对比分析查询
        if result := self._check_comparison(query):
            return result

        # 4. 复杂推理查询
        if result := self._check_complex_reasoning(query):
            return result

        # 5. 默认：事实查询
        return self._default_classification(query)

    def _check_simple_definition(self, query: str) -> Optional[QueryClassification]:
        """检查是否是简单定义查询"""
        matched_patterns = []

        for pattern in self.SIMPLE_DEFINITION_PATTERNS:
            if re.match(pattern, query):
                matched_patterns.append(pattern)

        if matched_patterns:
            # 额外检查：查询长度 < 20 字符
            if len(query) <= 20:
                logger.info(f"分类为简单定义查询: {query}")

                return QueryClassification(
                    query_type=QueryType.SIMPLE_DEFINITION,
                    confidence=0.9,
                    matched_patterns=matched_patterns,
                    recommended_strategy="simple",
                    skip_query_rewriting=True,  # 跳过查询改写
                    use_hybrid=False,           # 只用向量检索
                    top_k=5
                )

        return None

    def _check_calculation(self, query: str) -> Optional[QueryClassification]:
        """检查是否是计算类查询"""
        matched_patterns = []

        for pattern in self.CALCULATION_PATTERNS:
            if re.search(pattern, query):
                matched_patterns.append(pattern)

        if matched_patterns:
            logger.info(f"分类为计算类查询: {query}")

            return QueryClassification(
                query_type=QueryType.CALCULATION,
                confidence=0.85,
                matched_patterns=matched_patterns,
                recommended_strategy="calculation",
                skip_query_rewriting=False,
                use_hybrid=True,
                top_k=5
            )

        return None

    def _check_comparison(self, query: str) -> Optional[QueryClassification]:
        """检查是否是对比分析查询"""
        matched_patterns = []

        for pattern in self.COMPARISON_PATTERNS:
            if re.search(pattern, query):
                matched_patterns.append(pattern)

        if matched_patterns:
            logger.info(f"分类为对比分析查询: {query}")

            return QueryClassification(
                query_type=QueryType.COMPARISON,
                confidence=0.88,
                matched_patterns=matched_patterns,
                recommended_strategy="comparison",
                skip_query_rewriting=False,  # 使用 Multi-Query
                use_hybrid=True,
                top_k=8  # 需要更多文档
            )

        return None

    def _check_complex_reasoning(self, query: str) -> Optional[QueryClassification]:
        """检查是否是复杂推理查询"""
        matched_patterns = []

        for pattern in self.COMPLEX_REASONING_PATTERNS:
            if re.search(pattern, query):
                matched_patterns.append(pattern)

        if matched_patterns:
            logger.info(f"分类为复杂推理查询: {query}")

            return QueryClassification(
                query_type=QueryType.COMPLEX_REASONING,
                confidence=0.82,
                matched_patterns=matched_patterns,
                recommended_strategy="full",  # 完整流程
                skip_query_rewriting=False,
                use_hybrid=True,
                top_k=10
            )

        return None

    def _default_classification(self, query: str) -> QueryClassification:
        """默认分类"""
        logger.info(f"分类为事实查询（默认）: {query}")

        return QueryClassification(
            query_type=QueryType.FACTUAL,
            confidence=0.7,
            matched_patterns=[],
            recommended_strategy="standard",
            skip_query_rewriting=False,
            use_hybrid=True,
            top_k=5
        )

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_classifications": self.classification_count
        }


class AdaptiveRAGPipeline:
    """
    自适应 RAG 管道

    根据查询类型自动选择最优策略
    """

    def __init__(self, base_pipeline):
        """
        初始化自适应管道

        Args:
            base_pipeline: 基础 RAG 管道（EnhancedRAGPipeline）
        """
        self.base_pipeline = base_pipeline
        self.classifier = QueryClassifier()

        # 统计信息
        self.strategy_usage = {
            "simple": 0,
            "calculation": 0,
            "comparison": 0,
            "full": 0,
            "standard": 0
        }

    async def search_adaptive(
        self,
        query: str,
        generate_answer: bool = True,
        force_strategy: Optional[str] = None
    ) -> Dict:
        """
        自适应检索

        Args:
            query: 用户查询
            generate_answer: 是否生成答案
            force_strategy: 强制使用指定策略（用于测试）

        Returns:
            检索结果
        """
        # 分类查询
        classification = self.classifier.classify(query)

        # 选择策略
        strategy = force_strategy or classification.recommended_strategy

        logger.info(f"查询类型: {classification.query_type.value}, 策略: {strategy}")

        # 记录策略使用
        self.strategy_usage[strategy] = self.strategy_usage.get(strategy, 0) + 1

        # 执行对应策略
        if strategy == "simple":
            result = await self._simple_search(query, classification, generate_answer)
        elif strategy == "calculation":
            result = await self._calculation_search(query, classification, generate_answer)
        elif strategy == "comparison":
            result = await self._comparison_search(query, classification, generate_answer)
        elif strategy == "full":
            result = await self._full_search(query, classification, generate_answer)
        else:
            result = await self._standard_search(query, classification, generate_answer)

        # 添加分类信息
        result["classification"] = {
            "query_type": classification.query_type.value,
            "confidence": classification.confidence,
            "strategy": strategy
        }

        return result

    async def _simple_search(
        self,
        query: str,
        classification: QueryClassification,
        generate_answer: bool
    ) -> Dict:
        """
        简单查询策略

        跳过查询改写，只用向量检索
        节省时间: ~800ms
        """
        logger.info("执行简单查询策略（跳过查询改写）")

        # 直接向量检索
        result = await self.base_pipeline.search(
            query,
            use_hybrid=False,  # 只用向量
            top_k=classification.top_k
        )

        documents = result.documents

        # 生成答案
        answer = None
        if generate_answer and documents:
            answer_result = await self.base_pipeline._generate_answer(query, documents)
            answer = answer_result["answer"]

        return {
            "query": query,
            "documents": documents,
            "answer": answer,
            "strategy": "simple",
            "optimizations": ["skip_query_rewriting", "vector_only"]
        }

    async def _calculation_search(
        self,
        query: str,
        classification: QueryClassification,
        generate_answer: bool
    ) -> Dict:
        """
        计算类查询策略

        优先检索包含公式的文档
        """
        logger.info("执行计算类查询策略（优先公式）")

        # 混合检索
        result = await self.base_pipeline.search(
            query,
            use_hybrid=True,
            top_k=classification.top_k
        )

        documents = result.documents

        # 重排序：优先包含公式的文档
        documents = self._prioritize_formula_docs(documents)

        # 生成答案
        answer = None
        if generate_answer and documents:
            # 使用专门的计算类 prompt
            answer_result = await self._generate_calculation_answer(query, documents)
            answer = answer_result["answer"]

        return {
            "query": query,
            "documents": documents,
            "answer": answer,
            "strategy": "calculation",
            "optimizations": ["prioritize_formula"]
        }

    async def _comparison_search(
        self,
        query: str,
        classification: QueryClassification,
        generate_answer: bool
    ) -> Dict:
        """
        对比分析查询策略

        使用 Multi-Query 改写
        """
        logger.info("执行对比分析查询策略（Multi-Query）")

        # 使用 Multi-Query
        result = await self.base_pipeline.search_enhanced(
            query,
            use_query_rewriting=True,
            rewrite_strategy="multi_query",
            generate_answer=False
        )

        documents = result["documents"]

        # 生成答案
        answer = None
        if generate_answer and documents:
            # 使用专门的对比类 prompt
            answer_result = await self._generate_comparison_answer(query, documents)
            answer = answer_result["answer"]

        return {
            "query": query,
            "documents": documents,
            "answer": answer,
            "strategy": "comparison",
            "optimizations": ["multi_query"]
        }

    async def _full_search(
        self,
        query: str,
        classification: QueryClassification,
        generate_answer: bool
    ) -> Dict:
        """
        完整查询策略

        使用所有优化（HyDE + Multi-Query + 重排序）
        """
        logger.info("执行完整查询策略（所有优化）")

        # 完整流程
        result = await self.base_pipeline.search_enhanced(
            query,
            use_query_rewriting=True,
            rewrite_strategy="both",  # HyDE + Multi-Query
            generate_answer=generate_answer
        )

        return {
            **result,
            "strategy": "full",
            "optimizations": ["hyde", "multi_query", "reranking"]
        }

    async def _standard_search(
        self,
        query: str,
        classification: QueryClassification,
        generate_answer: bool
    ) -> Dict:
        """
        标准查询策略

        使用混合检索 + Multi-Query
        """
        logger.info("执行标准查询策略")

        result = await self.base_pipeline.search_enhanced(
            query,
            use_query_rewriting=True,
            rewrite_strategy="multi_query",
            generate_answer=generate_answer
        )

        return {
            **result,
            "strategy": "standard",
            "optimizations": ["multi_query", "hybrid_retrieval"]
        }

    def _prioritize_formula_docs(self, documents: List) -> List:
        """优先排序包含公式的文档"""
        formula_docs = []
        other_docs = []

        for doc in documents:
            # 检查是否包含公式
            has_formula = (
                "$$" in doc.content or
                "$" in doc.content or
                "=" in doc.content and any(op in doc.content for op in ["+", "-", "*", "/"])
            )

            if has_formula:
                formula_docs.append(doc)
            else:
                other_docs.append(doc)

        # 公式文档优先
        return formula_docs + other_docs

    async def _generate_calculation_answer(self, query: str, documents: List) -> Dict:
        """生成计算类答案（强调公式）"""
        # 构建上下文
        context_parts = []
        for i, doc in enumerate(documents[:5], 1):
            context_parts.append(f"[文档{i}]\n{doc.content}\n")

        context = "\n".join(context_parts)

        # 专门的计算类 prompt
        prompt = f"""基于以下文档回答计算问题。要求：

1. 明确给出计算公式（使用 LaTeX 格式：$$公式$$）
2. 解释公式中各参数的含义
3. 提供计算示例
4. 标注来源 [文档X]

文档：
{context}

问题：{query}

答案："""

        response = await self.base_pipeline.llm_client.chat.completions.create(
            model=self.base_pipeline.model,
            messages=[
                {"role": "system", "content": "你是专业的金融计算助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=800
        )

        return {"answer": response.choices[0].message.content.strip()}

    async def _generate_comparison_answer(self, query: str, documents: List) -> Dict:
        """生成对比分析答案（强调对比）"""
        context_parts = []
        for i, doc in enumerate(documents[:5], 1):
            context_parts.append(f"[文档{i}]\n{doc.content}\n")

        context = "\n".join(context_parts)

        # 专门的对比类 prompt
        prompt = f"""基于以下文档回答对比问题。要求：

1. 使用表格对比（Markdown 格式）
2. 列出关键差异点
3. 总结各自的优缺点
4. 标注来源 [文档X]

文档：
{context}

问题：{query}

答案："""

        response = await self.base_pipeline.llm_client.chat.completions.create(
            model=self.base_pipeline.model,
            messages=[
                {"role": "system", "content": "你是专业的金融分析助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )

        return {"answer": response.choices[0].message.content.strip()}

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = sum(self.strategy_usage.values())

        return {
            "total_queries": total,
            "strategy_usage": self.strategy_usage,
            "strategy_distribution": {
                k: v / total if total > 0 else 0
                for k, v in self.strategy_usage.items()
            },
            "classifier_stats": self.classifier.get_stats()
        }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    classifier = QueryClassifier()

    # 测试查询
    test_queries = [
        "什么是市盈率？",
        "如何计算 ROE？",
        "市盈率和市净率的区别",
        "为什么金融市场会波动？",
        "金融市场的功能有哪些？"
    ]

    print("\n" + "="*60)
    print("查询分类测试")
    print("="*60 + "\n")

    for query in test_queries:
        result = classifier.classify(query)

        print(f"查询: {query}")
        print(f"  类型: {result.query_type.value}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  推荐策略: {result.recommended_strategy}")
        print(f"  跳过改写: {result.skip_query_rewriting}")
        print(f"  使用混合: {result.use_hybrid}")
        print()
