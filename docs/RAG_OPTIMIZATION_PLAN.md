# RAG 系统算法优化方案

## 🎯 优化目标

1. **降低延迟** - 从当前 2-3 秒降至 < 500ms（秒出答案）
2. **提升准确性** - 召回率 85% → 95%，精确率 90% → 95%
3. **增强专业性** - 金融术语准确、计算公式正确、引用规范
4. **优化排版** - 结构化输出、Markdown 格式、表格/公式渲染

---

## 📊 当前性能瓶颈分析

基于可观测性数据，当前各阶段耗时：

| 阶段 | 当前耗时 | 占比 | 瓶颈 |
|------|---------|------|------|
| 查询改写 | 800-1200ms | 40% | LLM 调用（3 次） |
| 向量检索 | 200-300ms | 12% | 向量计算 |
| BM25 检索 | 100-150ms | 6% | 全文扫描 |
| 重排序 | 300-400ms | 15% | Cross-Encoder 计算 |
| 答案生成 | 500-800ms | 25% | LLM 生成 |
| 质量控制 | 50-100ms | 2% | 规则验证 |
| **总计** | **2000-3000ms** | **100%** | - |

**核心瓶颈**:
1. 查询改写的 3 次 LLM 调用（40% 耗时）
2. 答案生成的 LLM 调用（25% 耗时）
3. 重排序的 Cross-Encoder 计算（15% 耗时）

---

## 🚀 优化方案

### 方案 1: 智能缓存系统（降低延迟 60-80%）

#### 1.1 多层缓存架构

```python
class MultiLevelCache:
    """
    三层缓存架构

    L1: 内存缓存（LRU，容量 1000）- 命中率 30-40%
    L2: Redis 缓存（TTL 1 小时）- 命中率 20-30%
    L3: 语义缓存（向量相似度 > 0.95）- 命中率 10-15%

    总命中率: 60-85%
    """

    def __init__(self):
        self.l1_cache = LRUCache(maxsize=1000)  # 内存
        self.l2_cache = RedisCache(ttl=3600)    # Redis
        self.l3_cache = SemanticCache(threshold=0.95)  # 语义

    async def get(self, query: str) -> Optional[Dict]:
        # L1: 精确匹配
        if result := self.l1_cache.get(query):
            return result

        # L2: Redis 缓存
        if result := await self.l2_cache.get(query):
            self.l1_cache.set(query, result)
            return result

        # L3: 语义相似
        if result := await self.l3_cache.find_similar(query):
            self.l1_cache.set(query, result)
            return result

        return None
```

**预期效果**:
- 缓存命中时延迟: < 50ms（从 2000ms 降低 97.5%）
- 总体平均延迟: 500-800ms（考虑 60-85% 命中率）

#### 1.2 查询改写缓存

```python
class QueryRewriteCache:
    """缓存查询改写结果"""

    async def get_or_rewrite(self, query: str) -> List[str]:
        # 检查缓存
        cache_key = f"rewrite:{hash(query)}"
        if cached := await redis.get(cache_key):
            return json.loads(cached)

        # 执行改写
        rewritten = await self.rewriter.rewrite(query)

        # 缓存结果（1 小时）
        await redis.setex(cache_key, 3600, json.dumps(rewritten))

        return rewritten
```

**预期效果**: 查询改写从 800-1200ms → 10-50ms（缓存命中时）

---

### 方案 2: 查询路由与自适应策略（降低延迟 30-50%）

#### 2.1 查询分类器

```python
class QueryClassifier:
    """
    快速分类查询类型，选择最优策略

    类型：
    1. 简单定义查询 - 跳过查询改写，直接检索
    2. 计算类查询 - 优先检索公式和示例
    3. 对比分析查询 - 使用 Multi-Query
    4. 复杂推理查询 - 使用 HyDE + 多轮检索
    """

    # 使用轻量级分类器（FastText/小型 BERT）
    def classify(self, query: str) -> QueryType:
        # 规则 + 模型混合
        if self._is_simple_definition(query):
            return QueryType.SIMPLE_DEFINITION
        elif self._is_calculation(query):
            return QueryType.CALCULATION
        elif self._is_comparison(query):
            return QueryType.COMPARISON
        else:
            return QueryType.COMPLEX_REASONING

    def _is_simple_definition(self, query: str) -> bool:
        # 快速规则判断
        patterns = [
            r"^什么是.{1,10}[？?]$",
            r"^.{1,10}的定义",
            r"^解释.{1,10}"
        ]
        return any(re.match(p, query) for p in patterns)
```

#### 2.2 自适应策略选择

```python
class AdaptiveRAGPipeline:
    """根据查询类型自适应选择策略"""

    async def search_adaptive(self, query: str) -> Dict:
        # 分类查询
        query_type = self.classifier.classify(query)

        # 选择策略
        if query_type == QueryType.SIMPLE_DEFINITION:
            # 简单查询：跳过改写，只用向量检索
            return await self._simple_search(query)

        elif query_type == QueryType.CALCULATION:
            # 计算查询：优先检索公式
            return await self._calculation_search(query)

        elif query_type == QueryType.COMPARISON:
            # 对比查询：使用 Multi-Query
            return await self._comparison_search(query)

        else:
            # 复杂查询：完整流程
            return await self._full_search(query)

    async def _simple_search(self, query: str) -> Dict:
        """简单查询：跳过改写，节省 800ms"""
        docs = await self.vector_search(query, top_k=5)
        answer = await self.generate_answer(query, docs)
        return {"answer": answer, "strategy": "simple"}
```

**预期效果**:
- 简单查询（40% 占比）: 2000ms → 800ms（节省 60%）
- 计算查询（20% 占比）: 2000ms → 1200ms（节省 40%）
- 总体平均延迟: 1200-1500ms

---

### 方案 3: 并行化与异步优化（降低延迟 20-30%）

#### 3.1 并行检索

```python
async def parallel_retrieval(self, query: str) -> List[Document]:
    """并行执行多种检索"""

    # 同时执行 3 种检索
    vector_task = asyncio.create_task(self.vector_search(query))
    bm25_task = asyncio.create_task(self.bm25_search(query))
    lexical_task = asyncio.create_task(self.lexical_search(query))

    # 等待所有完成
    vector_results, bm25_results, lexical_results = await asyncio.gather(
        vector_task, bm25_task, lexical_task
    )

    # 融合结果
    return self.fusion(vector_results, bm25_results, lexical_results)
```

**当前**: 串行执行 200ms + 100ms + 50ms = 350ms
**优化后**: 并行执行 max(200ms, 100ms, 50ms) = 200ms
**节省**: 150ms（43%）

#### 3.2 流式输出（提升用户体验）

```python
async def stream_answer(self, query: str):
    """流式生成答案，边检索边输出"""

    # 1. 快速返回检索结果（200ms）
    yield {"type": "documents", "data": await self.retrieve(query)}

    # 2. 流式生成答案（每 50ms 输出一段）
    async for chunk in self.llm_stream(query, documents):
        yield {"type": "answer_chunk", "data": chunk}

    # 3. 最后返回来源引用
    yield {"type": "sources", "data": self.extract_sources(documents)}
```

**用户感知延迟**: 200ms（首屏）vs 2000ms（完整）

---

### 方案 4: 向量索引优化（降低延迟 10-20%）

#### 4.1 HNSW 索引 + 量化

```python
class OptimizedVectorIndex:
    """优化的向量索引"""

    def __init__(self):
        # 使用 HNSW 索引（比暴力搜索快 10-100 倍）
        self.index = hnswlib.Index(space='cosine', dim=768)
        self.index.init_index(
            max_elements=100000,
            ef_construction=200,  # 构建时精度
            M=16                  # 连接数
        )

        # 使用 PQ 量化（减少内存 75%，速度提升 2-4 倍）
        self.quantizer = ProductQuantizer(
            n_subvectors=8,
            n_bits=8
        )

    def search(self, query_vector: np.ndarray, top_k: int = 10):
        # 设置搜索精度
        self.index.set_ef(50)  # 搜索时精度

        # 快速搜索
        labels, distances = self.index.knn_query(query_vector, k=top_k)
        return labels, distances
```

**预期效果**:
- 向量检索: 200-300ms → 50-100ms（提升 2-4 倍）
- 内存占用: 4GB → 1GB（减少 75%）

#### 4.2 分层索引

```python
class HierarchicalIndex:
    """分层索引：粗排 + 精排"""

    def __init__(self):
        # L1: 粗排索引（低精度，快速）
        self.coarse_index = self._build_coarse_index()

        # L2: 精排索引（高精度，慢速）
        self.fine_index = self._build_fine_index()

    async def search(self, query: str, top_k: int = 5):
        # 粗排：快速召回 top-100（50ms）
        candidates = await self.coarse_index.search(query, top_k=100)

        # 精排：精确排序 top-5（100ms）
        results = await self.fine_index.rerank(query, candidates, top_k=top_k)

        return results
```

**预期效果**: 检索 + 重排序: 500-700ms → 150-200ms

---

### 方案 5: 模型优化（提升准确性 + 降低延迟）

#### 5.1 专用金融 Embedding 模型

```python
class FinancialEmbedding:
    """
    金融领域专用 Embedding

    方案 1: 微调 BGE-base-zh-v1.5
    - 使用金融语料微调（10 万条金融 QA 对）
    - 预期提升: 召回率 +5-10%

    方案 2: 使用更大模型
    - BGE-large-zh-v1.5（1024 维）
    - 预期提升: 召回率 +3-5%，延迟 +20%
    """

    def __init__(self, model_type: str = "fine-tuned"):
        if model_type == "fine-tuned":
            # 加载微调模型
            self.model = SentenceTransformer("./models/bge-finance-zh")
        else:
            # 使用原始模型
            self.model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
```

#### 5.2 轻量级 Reranker

```python
class LightweightReranker:
    """
    轻量级重排序模型

    当前: BGE-reranker-base（300-400ms）
    优化: 使用蒸馏模型（100-150ms）
    """

    def __init__(self):
        # 使用知识蒸馏的轻量级模型
        self.model = CrossEncoder("./models/reranker-distilled")

    def rerank(self, query: str, documents: List[str]) -> List[float]:
        # 批量计算（更快）
        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs, batch_size=32)
        return scores
```

**预期效果**: 重排序 300-400ms → 100-150ms（提升 2-3 倍）

---

### 方案 6: 答案生成优化（提升专业性 + 格式）

#### 6.1 结构化 Prompt

```python
class StructuredAnswerGenerator:
    """结构化答案生成"""

    PROMPT_TEMPLATE = """你是一个专业的金融知识助手。请基于以下文档回答问题。

【核心要求】
1. 使用 Markdown 格式
2. 金融术语必须准确（如：市盈率 P/E，市净率 P/B）
3. 公式使用 LaTeX 格式：$公式$
4. 引用来源：[文档X]

【文档】
{context}

【问题】
{query}

【回答格式】
## 核心定义
[简洁定义，1-2 句话]

## 详细说明
[详细解释，分点说明]

## 计算公式（如适用）
$$公式$$

## 实例说明（如适用）
[具体例子]

## 参考来源
- [文档1] ...
- [文档2] ...

请严格按照上述格式回答："""

    async def generate(self, query: str, documents: List[Document]) -> str:
        # 构建上下文
        context = self._build_context(documents)

        # 生成答案
        prompt = self.PROMPT_TEMPLATE.format(
            context=context,
            query=query
        )

        response = await self.llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是专业的金融知识助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 更确定性
            max_tokens=1000
        )

        return response.choices[0].message.content
```

#### 6.2 后处理优化

```python
class AnswerPostProcessor:
    """答案后处理"""

    def process(self, answer: str) -> Dict:
        """
        后处理优化：
        1. 验证金融术语准确性
        2. 格式化公式（LaTeX）
        3. 美化表格
        4. 添加目录（长答案）
        """

        # 1. 术语校验
        answer = self._validate_financial_terms(answer)

        # 2. 公式格式化
        answer = self._format_formulas(answer)

        # 3. 表格美化
        answer = self._beautify_tables(answer)

        # 4. 添加目录
        if len(answer) > 500:
            answer = self._add_toc(answer)

        return {
            "answer": answer,
            "metadata": {
                "has_formula": "$$" in answer,
                "has_table": "|" in answer,
                "word_count": len(answer)
            }
        }

    def _validate_financial_terms(self, answer: str) -> str:
        """验证并修正金融术语"""
        corrections = {
            "市盈率": "市盈率（P/E Ratio）",
            "市净率": "市净率（P/B Ratio）",
            "ROE": "净资产收益率（ROE）",
            "ROA": "总资产收益率（ROA）"
        }

        for term, correct in corrections.items():
            # 首次出现时添加英文注释
            answer = re.sub(
                f"(?<!（){term}(?!（)",
                correct,
                answer,
                count=1
            )

        return answer
```

---

### 方案 7: 预计算与预热（降低冷启动延迟）

#### 7.1 热门查询预计算

```python
class QueryPrecomputer:
    """预计算热门查询"""

    # 热门查询列表（基于日志分析）
    HOT_QUERIES = [
        "什么是市盈率？",
        "如何计算 ROE？",
        "金融市场的功能",
        # ... 100 个热门查询
    ]

    async def precompute_hot_queries(self):
        """预计算热门查询（每天凌晨执行）"""
        for query in self.HOT_QUERIES:
            # 预计算并缓存
            result = await self.pipeline.search_enhanced(query)
            await self.cache.set(query, result, ttl=86400)

        logger.info(f"预计算完成: {len(self.HOT_QUERIES)} 个查询")
```

#### 7.2 模型预热

```python
class ModelWarmer:
    """模型预热"""

    async def warmup(self):
        """启动时预热所有模型"""
        # 1. Embedding 模型
        dummy_text = "测试文本"
        _ = self.embedding_model.encode(dummy_text)

        # 2. Reranker 模型
        _ = self.reranker.predict([["query", "document"]])

        # 3. LLM 连接
        _ = await self.llm_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10
        )

        logger.info("模型预热完成")
```

---

## 📊 优化效果预测

### 延迟优化

| 优化方案 | 延迟降低 | 实施难度 | 优先级 |
|---------|---------|---------|--------|
| 智能缓存 | 60-80% | 中 | 🔴 高 |
| 查询路由 | 30-50% | 中 | 🔴 高 |
| 并行化 | 20-30% | 低 | 🟡 中 |
| 向量优化 | 10-20% | 高 | 🟡 中 |
| 模型优化 | 10-15% | 高 | 🟢 低 |
| 预计算 | 5-10% | 低 | 🟢 低 |

**综合效果**:
- 当前平均延迟: 2000-3000ms
- 优化后平均延迟: **300-500ms**（缓存命中）/ **800-1200ms**（缓存未命中）
- **提升**: 4-6 倍

### 准确性优化

| 优化方案 | 准确性提升 | 实施难度 | 优先级 |
|---------|-----------|---------|--------|
| 金融 Embedding | +5-10% | 高 | 🔴 高 |
| 查询路由 | +3-5% | 中 | 🔴 高 |
| 结构化 Prompt | +5-8% | 低 | 🟡 中 |
| 术语校验 | +2-3% | 低 | 🟡 中 |

**综合效果**:
- 召回率: 85% → **93-95%**
- 精确率: 90% → **95-97%**

---

## 🛠️ 实施计划

### 阶段 1: 快速优化（1 周）

**目标**: 延迟降低 50%，立即见效

1. **实现智能缓存**（2 天）
   - Redis 缓存
   - LRU 内存缓存
   - 语义缓存

2. **查询路由**（2 天）
   - 规则分类器
   - 简单查询快速通道

3. **并行化检索**（1 天）
   - 异步并行
   - 流式输出

4. **测试验证**（2 天）

### 阶段 2: 深度优化（2 周）

**目标**: 准确性提升 10%，延迟再降低 30%

1. **向量索引优化**（4 天）
   - HNSW 索引
   - 量化压缩

2. **模型优化**（5 天）
   - 微调 Embedding
   - 轻量级 Reranker

3. **答案生成优化**（3 天）
   - 结构化 Prompt
   - 术语校验

4. **测试验证**（2 天）

### 阶段 3: 精细优化（1 周）

**目标**: 用户体验完美

1. **预计算系统**（2 天）
2. **监控告警**（2 天）
3. **A/B 测试**（2 天）
4. **文档完善**（1 天）

---

## 📈 监控指标

### 性能指标
- P50 延迟 < 500ms
- P95 延迟 < 1500ms
- P99 延迟 < 2500ms
- 缓存命中率 > 60%

### 质量指标
- 召回率 > 93%
- 精确率 > 95%
- 用户满意度 > 4.5/5
- 答案采纳率 > 85%

---

## 🎯 总结

通过 7 大优化方案，可以实现：

✅ **延迟降低 75-85%**: 2000-3000ms → 300-500ms（缓存命中）
✅ **准确性提升 10-15%**: 召回率 85% → 95%，精确率 90% → 95%
✅ **专业性增强**: 金融术语准确、公式规范、引用完整
✅ **格式优化**: Markdown 结构化、表格美化、目录导航

**核心优化**:
1. 智能缓存（最高优先级，立即见效）
2. 查询路由（快速实施，效果显著）
3. 并行化（低成本，高收益）

**下一步**: 立即实施阶段 1 的快速优化方案！
