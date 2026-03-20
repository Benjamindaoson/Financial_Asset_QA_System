# 硅谷级 AI 架构师视角：3 分钟逐字稿代码对照评估

> 基于全代码遍历，逐条核对逐字稿表述与实现的一致性，并给出修正建议。

---

## 一、总体评价

**结构设计：A+**  
前 40 秒给全局视图、模块划分、设计理由，再通过查询走一遍协作，最后收技术决策和扩展性，符合 CTO 的认知路径。

**代码一致性：B+**  
多数表述与实现一致，但有若干处与代码不符，需修正以避免现场被追问时露馅。

---

## 二、逐段核对与修正建议

### 【0:00 - 0:40】系统整体介绍 + 架构模块划分

| 逐字稿表述 | 代码事实 | 评估 |
|------------|----------|------|
| 「五个模块：Gateway、路由、执行、校验、生成」 | 与 `app/api/routes.py`、`app/agent/core.py` 分层一致 | ✅ 正确 |
| 「QueryRouter 纯规则」 | `app/routing/router.py` 无 LLM 调用，`classify_async` 直接调 `classify` | ✅ 正确 |
| 「MARKET、KNOWLEDGE、NEWS、HYBRID 四种」 | `QueryType` 枚举 L14-18 | ✅ 正确 |
| 「合规拦截：投资建议类直接拒答」 | `refuses_advice` 分支 L787-791，不进入 tool plan | ✅ 正确 |
| 「行情通道：Finnhub、Stooq、Alpha Vantage、yfinance 四级 fallback」 | `service.py` L549-573：Finnhub → Stooq → Alpha Vantage → yfinance | ✅ 正确 |
| 「知识通道走 HybridRAGPipeline，向量加 BM25 混合检索」 | **部分正确**：`HybridRAGPipeline.search_grounded()` 确实实现 vector+BM25+RRF，但 **BM25 索引需显式 build**。`build_vector_index.py` 未调用 `build_bm25_index()`，默认部署下 `bm25_index=None`，实际走 **纯向量 + Reranker** | ⚠️ 需修正 |
| 「DataValidator 校验数据完整性，数据全部缺失就不生成」 | `should_block_response` = `not can_analyze`，`can_analyze` = 任一数据源有有效数据 | ✅ 正确 |
| 「ResponseGuard：每个数字必须能在工具返回中找到溯源」 | **过度表述**。实际逻辑（L34-43）：`grounded_numbers` 非空时，要求 `grounded_numbers & mentioned_numbers` 非空，即 **至少有一个** LLM 数字来自工具，非「每个都必须」 | ⚠️ 需修正 |
| 「LLM 是最后一个环节，不决定调什么工具」 | `_build_tool_plan` 纯规则，LLM 仅用于 `ResponseGenerator` | ✅ 正确 |

**修正建议**：
- 知识通道：「向量加 BM25 混合检索」→「向量检索为主，可选 BM25 融合（需预建 BM25 索引）」
- ResponseGuard：「每个数字必须」→「LLM 输出中的数字需能在工具返回中找到对应，避免凭空编造」

---

### 【0:40 - 1:00】Q1：行情查询

| 逐字稿表述 | 代码事实 | 评估 |
|------------|----------|------|
| 「阿里巴巴当前股价」→ MARKET | `CURRENT_PRICE_KEYWORDS` 含「当前」，`requires_price=True` | ✅ 正确 |
| 「get_price 和 get_change」 | `_build_tool_plan` L279-285：requires_price 时加 get_price，并自动加 get_change(7天) | ✅ 正确 |
| 「价格从 Finnhub 拿」 | get_price 优先 Finnhub | ✅ 正确 |
| 「Redis 缓存 TTL 60 秒」 | `config.py` CACHE_TTL_PRICE=60 | ✅ 正确 |
| 「market 模板：近期走势+技术面观察+风险提示」 | `prompts.yaml` L167-176 三段式 | ✅ 正确 |

---

### 【1:00 - 1:25】Q2：趋势分析

| 逐字稿表述 | 代码事实 | 评估 |
|------------|----------|------|
| 「BABA 最近 7 天涨跌」→ HYBRID | 含「涨跌」+ symbol，`requires_change` 且 `requires_history`（L211） | ✅ 正确 |
| 「get_price、get_history、get_change 并行」 | `_execute_tools_parallel` 并发执行 | ✅ 正确 |
| 「Tavily 做新闻搜索」 | `requires_web` 时 `search_web`，调用 `WebSearchService`（Tavily） | ✅ 正确 |
| 「_build_tool_plan 纯规则，根据 requires_* 动态组合」 | L264-301 完全按 route 的 requires_* 组合 | ✅ 正确 |
| 「事件归因按高、中、低关联度分级」 | `prompts.yaml` L210-211：「🔴 高关联」「🟡 中关联」「🔵 低关联」 | ✅ 正确 |
| 「hybrid 模板：走势概述+事件归因+当前状态」 | L190-218 | ✅ 正确 |

---

### 【1:25 - 2:00】Q3：RAG 知识问答

| 逐字稿表述 | 代码事实 | 评估 |
|------------|----------|------|
| 「什么是市盈率」→ KNOWLEDGE，只触发 search_knowledge | 正确 | ✅ 正确 |
| 「三级检索链路」 | 1) token-match 2) vector+reranker 3) 无结果时 Tavily 补充 | ✅ 正确 |
| 「第一级：token-match，jieba 分词做 token 重叠」 | **错误**。`_search_local_documents` 使用 `_tokenize_text`：正则 `re.split` + 中文 2-4 字滑动窗口，**不用 jieba**。jieba 仅用于 HybridRAGPipeline 的 BM25 分支 | ❌ 需修正 |
| 「QUERY_EXPANSIONS：市盈率→PE、price-to-earnings」 | `pipeline.py` L17：`"市盈率": {"pe", "price-to-earnings", "valuation", "估值"}` | ✅ 正确 |
| 「第二级：HybridRAGPipeline，BGE 向量+BM25 并行，RRF 融合 k=60」 | `HybridRAGPipeline.search_grounded` L236-341 实现此逻辑，但 **bm25_index 默认 None**，未 build 时退化为纯向量 | ⚠️ 需修正 |
| 「金融领域混合策略召回率比单一向量高约 30%」 | 无代码或实验支撑，属经验性说法 | ⚠️ 建议删除或改为「设计上兼顾语义与关键词」 |
| 「第三级：BGE-reranker，score 阈值 0.3，Top-3」 | `score_threshold=0.3`，`RAG_TOP_N=3` | ✅ 正确 |
| 「knowledge 模板：定义+公式+应用举例+注意事项」 | L228-236 四段式 | ✅ 正确 |
| 「知识库不足时自动降级到 Tavily 补充」 | `_search_knowledge_async` L170-182：`no_relevant_content` 且 TAVILY_API_KEY 时触发 | ✅ 正确 |

**修正建议**：
- 「jieba 分词做 token 重叠」→「基于正则和中文滑动窗口的 token 重叠匹配」
- 「BGE 向量+BM25 并行」→「BGE 向量检索，若预建了 BM25 索引则与 BM25 结果 RRF 融合」（或直接说「向量+精排」以保守表述）

---

### 【2:00 - 2:20】Q4：合规拒答

| 逐字稿表述 | 代码事实 | 评估 |
|------------|----------|------|
| 「阿里巴巴明天会涨吗」→ refuses_advice | `ADVICE_KEYWORDS` 含「会涨吗」「会跌吗」 | ✅ 正确 |
| 「执行层、校验层、生成层全部跳过」 | L787-791 直接 yield chunk + done，return | ✅ 正确 |
| 「拒答同时引导可问：价格、走势、波动率、回撤、公告」 | L788：`"你可以继续问我该标的的价格、历史走势、波动率、最大回撤或最新公告。"` | ✅ 正确 |
| 「合规拦截在路由层而不是 Prompt 层」 | 正确，refuses_advice 在 `classify` 中设置，早于 tool 执行 | ✅ 正确 |

---

### 【2:20 - 2:50】关键技术决策

| 逐字稿表述 | 代码事实 | 评估 |
|------------|----------|------|
| 「规则路由延迟 10ms，LLM 分类 300-500ms」 | 无实测数据，属合理量级估计 | ⚠️ 可保留，建议加「量级上」 |
| 「LLM 挂了规则路由照常」 | 规则路由不依赖 LLM | ✅ 正确 |
| 「DeepSeek 成本约十分之一」 | README 表述 | ✅ 可引用 |
| 「blocks 事件先于 analysis_chunk」 | `core.py` L834-835 先 yield blocks，L904 再 yield analysis_chunk | ✅ 正确 |
| 「用户体感等待从 25 秒压缩到 1-2 秒」 | blocks 约 1.5s（知识类）或 11s（行情类），分析流式输出，首字约 3s | ⚠️ 「1-2 秒」对知识类成立，行情类首屏更久，建议改为「数据卡片先于分析出现，显著缩短可感知等待」 |

---

## 三、修正后的关键表述（可直接替换）

### RAG 检索链路（Q3 口述修正版）

> 第一级，token-match 快速路径。`_search_local_documents` 用正则和中文滑动窗口做 token 重叠匹配，加上 QUERY_EXPANSIONS 同义词扩展——比如「市盈率」自动映射到 PE、price-to-earnings。无模型推理，命中直接返回。
>
> 第二级，token-match 没结果时，走向量检索加 Reranker。BGE-base-zh 向量检索 Top-K，BGE-reranker 做 Cross-Encoder 精排，score 阈值 0.3，返回 Top-3。若部署时预建了 BM25 索引，会与 BM25 结果做 RRF 融合，进一步兼顾关键词匹配。
>
> 第三级，知识库仍无结果且配置了 Tavily 时，自动补充网络搜索。

### ResponseGuard（架构介绍修正版）

> ResponseGuard 在 LLM 生成之后做输出校验——要求 LLM 输出中出现的数字能在工具返回的原始数据中找到对应，避免凭空编造。注意是「有对应」而非「逐字逐句溯源」，实现上采用集合交集校验。

---

## 四、架构师视角的额外建议

### 1. 可补充的设计亮点

- **数据与排版分离**：blocks（chart/table/key_metrics）由 `_compose_answer` 编排，早于 LLM 输出推送，前端可先渲染数据再流式显示分析，避免 Markdown 表格错乱。
- **降级路径清晰**：ChromaDB 不可用时退化为 token-match；LLM 不可用时直接输出 blocks + 模板文本，前端不白屏。

### 2. 可预见的 CTO 追问及应答

| 追问 | 建议应答 |
|------|----------|
| 「为什么不用 LangChain？」 | 金融场景需要显式控制数据流，保证行情必走 API、数值可溯源。LangChain 的 Agent 抽象对数据流控制不足，难以满足审计要求。 |
| 「BM25 实际用了吗？」 | 当前索引构建脚本未调用 `build_bm25_index`，默认是纯向量+精排。若需要更高召回，可在索引构建阶段加入 BM25，代码已支持。 |
| 「ResponseGuard 能防住所有幻觉吗？」 | 不能。它只校验数字是否来自工具，不校验逻辑推理或事实性陈述。设计上是「数值可追溯」的底线保障，不是完整幻觉解决方案。 |

### 3. 战略连接句的可选强化

原句：「接入快讯流和研报库，替换内部 API，直接作为产品化基础架构。」

可加强为：「架构上，知识库灌入、行情数据源、新闻源都是可插拔的。接入华尔街见闻的快讯流和研报库作为 context source，行情服务替换为内部 API，这套 Pipeline 可以直接作为产品化基础架构，无需推倒重来。」

---

## 五、总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 叙事结构 | A+ | 全局→协作→决策，符合 CTO 认知路径 |
| 模块划分准确性 | A | 五层划分与代码一致 |
| 技术细节准确性 | B+ | 多数正确，RAG token-match、BM25 使用、ResponseGuard 表述需微调 |
| 可演示性 | A | 四个查询覆盖主要路径，可操作性强 |
| 战略连接 | A | 收尾自然衔接到产品化与扩展性 |

**建议**：按本文修正 RAG 与 ResponseGuard 的表述后，该逐字稿可放心用于 CTO 演示。若 CTO 追问 BM25，可如实说明「当前默认未启用，但架构已支持，索引构建时可开启」。
