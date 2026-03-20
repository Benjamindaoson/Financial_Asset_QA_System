# FinSight AI 演示视频逐字稿 — 完整数据提取

> 基于全代码遍历，精确代码引用（文件路径 + 行号），供撰写 3 分钟演示视频逐字稿使用。

---

## 1. 查询路由逻辑

### 1.1 QueryRouter.classify_async() 分类规则

**代码位置**：`backend/app/routing/router.py`

| QueryType | 触发条件 | 代码行 |
|-----------|----------|--------|
| `MARKET` | `has_market` 且非 `has_news`/`has_report` | 156-157 |
| `KNOWLEDGE` | 非 market/news/report | 162 |
| `NEWS` | `has_news` 或 `has_report` 且非 market | 158-159 |
| `HYBRID` | `has_market` 且 (`has_news` 或 `has_report`) | 154-155 |

**关键词集合**（`router.py` 第 43-118 行）：

```python
# MARKET_KEYWORDS (L44-62)
"价格","股价","行情","走势","涨跌","涨幅","跌幅","市值","quote","price","k线","历史","chart","trend","volume","etf","债券","bond"

# KNOWLEDGE_KEYWORDS (L63-76)
"什么是","定义","含义","解释","如何","计算","公式","概念","区别","what is","definition","meaning","difference"

# NEWS_KEYWORDS (L77-95)
"为什么","原因","新闻","事件","公告","财报","消息","影响","最近","最新","today","yesterday","news","event","reason","earnings"

# REPORT_KEYWORDS (L100)
"季度","财报","业绩","earnings","10-k","10-q","8-k","filing","sec","edgar"
```

**requires_* 映射逻辑**（L174-212）：

- `MARKET`：requires_price（当前价关键词 或 无其他需求）、requires_change、requires_history、requires_info、requires_metrics
- `KNOWLEDGE`：requires_knowledge = True
- `NEWS`：requires_web = True，requires_sec = has_report
- `HYBRID`：requires_price/change/history/info/web/sec/knowledge 按需

### 1.2 refuses_advice 拒答关键词

**代码位置**：`backend/app/routing/router.py` 第 103-117 行

```python
ADVICE_KEYWORDS = {
    "可以买", "值得买吗", "该买吗", "买入", "卖出", "推荐", "投资建议",
    "目标价", "会涨吗", "会跌吗", "should i buy", "buy or sell",
    "target price", "recommend",
}
```

**触发逻辑**：`route.refuses_advice = self._contains_any(cleaned, lowered, self.ADVICE_KEYWORDS)`（L174）

### 1.3 路由决策：纯规则 vs LLM

**当前实现**：**纯规则路由**。`AgentCore` 使用 `QueryRouter`（`app/agent/core.py` L91），未调用 `LLMRouter` 或 `HybridRouter`。

- `classify_async` 实际调用 `classify`（L139-140），无 LLM 参与
- `LLMRouter`（`app/routing/llm_router.py`）和 `HybridRouter`（`app/routing/hybrid_router.py`）存在但未接入主流程

---

## 2. Pipeline 步骤与 Tool Plan

### 2.1 QueryType → Tool Plan 映射

**代码位置**：`backend/app/agent/core.py` 第 264-301 行 `_build_tool_plan()`

| 条件 | Tool Plan |
|------|-----------|
| `requires_comparison` 且 symbols≥2 | `[compare_assets]` |
| `MARKET`/`HYBRID` + symbol | 按 requires_* 添加：get_price, get_change, get_history, get_info, get_metrics |
| `requires_price` 且非 requires_change | 自动加 get_change(7天)（L283-285） |
| `requires_knowledge` | search_knowledge |
| `requires_web` | search_web |
| `requires_sec` | search_sec |

**示例映射**：

| QueryType | 典型问题 | Tool Plan |
|-----------|----------|-----------|
| MARKET（纯价格） | "苹果股价多少" | [get_price, get_change], search_knowledge 若 requires_knowledge |
| MARKET（涨跌） | "苹果最近涨了多少" | [get_change, get_history], ... |
| MARKET（历史） | "苹果过去一个月走势" | [get_history], ... |
| KNOWLEDGE | "什么是市盈率" | [search_knowledge] |
| NEWS | "为什么特斯拉涨" | [search_web] |
| HYBRID | "阿里巴巴最近为何大涨" | [get_price, get_change, get_history, search_web, search_sec, search_knowledge]（按 route） |
| 对比 | "AAPL 和 MSFT 对比" | [compare_assets] |

### 2.2 _build_tool_plan() 完整逻辑

```python
# backend/app/agent/core.py L264-301
if route.requires_comparison and len(route.symbols) >= 2:
    add_tool("compare_assets", ...)
    return plan

if route.query_type in {QueryType.MARKET, QueryType.HYBRID} and primary_symbol:
    if route.requires_price: add_tool("get_price", ...); [若!requires_change则add get_change(7天)]
    if route.requires_change: add_tool("get_change", ...)
    if route.requires_history: add_tool("get_history", ...)
    if route.requires_info: add_tool("get_info", ...)
    if route.requires_metrics: add_tool("get_metrics", ...)

if route.requires_knowledge: add_tool("search_knowledge", ...)
if route.requires_web: add_tool("search_web", ...)
if route.requires_sec: add_tool("search_sec", ...)
```

---

## 3. 反幻觉机制

### 3.1 DataValidator.validate_tool_results()

**代码位置**：`backend/app/analysis/validator.py` 第 16-125 行

**校验规则**（按工具计分）：

| 工具 | 通过条件 | 得分 | 不通过时 missing |
|------|----------|------|------------------|
| get_price | `data.price is not None` | 20 | "实时价格" |
| get_history | `len(data.data) >= 20` | 20 | "历史行情" |
| get_change | `data.change_pct is not None` | 10 | "涨跌幅" |
| get_info | `data.name` 存在 | 10 | "公司资料" |
| get_metrics | `data.annualized_volatility is not None` | 20 | "收益风险指标" |
| search_web | `data.results` 非空 | 10 | "新闻检索" |
| search_sec | `data.results` 非空 | 10 | "SEC/财报检索" |
| search_knowledge | `data.documents` 非空 | 20 | "知识库检索" |

**confidence 分级**（L104-108）：
- score ≥ 75 → level = "high"
- score ≥ 45 → level = "medium"
- 否则 → level = "low"

### 3.2 should_block_response()

**代码位置**：`backend/app/analysis/validator.py` 第 127-129 行

```python
def should_block_response(validation: Dict[str, Any]) -> bool:
    return not validation.get("can_analyze", False)
```

`can_analyze` = `has_price or has_history or has_news or has_sec or has_knowledge`（L122）

即：**任一数据源有有效数据则不 block**；全部缺失则 block。

### 3.3 ResponseGuard.validate()

**代码位置**：`backend/app/agent/core.py` 第 30-56 行

**逻辑**：
1. 从 `tool_results` 递归收集所有 int/float 到 `grounded_numbers`（`_collect_numbers`）
2. 用正则 `r"\d+(?:\.\d+)?"` 提取 LLM 输出中的数字到 `mentioned_numbers`
3. 返回 `bool(grounded_numbers & mentioned_numbers)`：**至少有一个 LLM 提到的数字来自工具 payload 则通过**

注意：当前实现是「有交集即通过」，不是「LLM 中所有数字都必须在 grounded 中」。

### 3.4 hard_guardrails

**README 描述**（`README.md` L386-395）中提到的 `hard_guardrails` 在**当前代码中未实现**。`ResponseGenerator` 仅使用 `prompts.yaml` 的 generator system_prompt（`app/core/response_generator.py` L53, L109），无代码注入。

README 中的设计为：
```
绝对禁令（Guardrails）：
1. 你的回答必须100%基于用户提供的上下文数据...
2. 禁止预测未来走势、买卖推荐、目标价等投资建议。
3. 若数据不足，必须明确说明"缺乏足够数据支撑"...
4. 必须使用简体中文回答...
5. 禁止使用英文作为小节标题或术语。
```

---

## 4. RAG Pipeline

### 4.1 _search_knowledge_async 实际流程（Agent 调用入口）

**代码位置**：`backend/app/agent/core.py` 第 115-191 行

1. **Token-match 优先**：`_search_local_documents(query)`，有结果则直接返回
2. **向量+rerank**：ChromaDB 可用且 token-match 为空时，调用 `search_grounded(query, score_threshold=0.3)`
3. **向量失败**：回退到 token-match
4. **无结果 + Tavily**：触发 `search_service.search()` 补充 web 搜索

### 4.2 RAGPipeline.search_grounded()（Agent 实际使用的向量检索）

**代码位置**：`backend/app/rag/pipeline.py` 第 290-346 行

- **向量 Top-K**：`settings.RAG_TOP_K` = **5**（`config.py` L58）
- **Rerank 阈值**：`score_threshold` 默认 **0.3**（Agent 传入，`core.py` L139）
- **Top-N**：`settings.RAG_TOP_N` = **3**（`config.py` L59）

流程：embedding → ChromaDB query(n_results=RAG_TOP_K) → FlagReranker → 过滤 score≥threshold → 取 Top-N

### 4.3 HybridRAGPipeline 与实际调用路径

**代码位置**：`backend/app/rag/hybrid_pipeline.py`

`HybridRAGPipeline` 重写了 `search()`（L151），实现向量+BM25+RRF+rerank，但**未重写 `search_grounded()`**。

Agent 调用的是 `search_grounded()`（`core.py` L139），因此实际走的是**父类 RAGPipeline.search_grounded()**，即**纯向量 + Reranker**，无 BM25/RRF。

若未来改为调用 `search()`，则 HybridRAGPipeline 参数为：
- 向量 Top-K：10（父类 RAGPipeline.search 中）
- BM25 Top-K：20（L181）
- RRF k：60（L89）
- Rerank 后 Top-N：3（L217）
- Rerank 分数阈值：0.3（L207）

### 4.4 token-match (_search_local_documents)

**代码位置**：`backend/app/rag/pipeline.py` 第 184-213 行

**逻辑**：
1. `_tokenize_text(query)`：分词为 tokens（2+ 字符，含中文 2-4 字滑动窗口）
2. `QUERY_EXPANSIONS` 扩展同义词（如「市盈率」→ pe, price-to-earnings 等）
3. 遍历 `_local_documents`，计算 `overlap = len(query_tokens & doc.tokens)`
4. 若 overlap=0 但 expanded_terms 在 content 中出现，overlap=1
5. 按 overlap 排序，取 Top `settings.RAG_TOP_N`（3）

### 4.5 知识库文档

**加载路径**：`backend/app/rag/pipeline.py` 第 68-127 行 `_load_local_documents()`

- `data/knowledge/*.md`
- `data/raw_data/knowledge/*.md`
- `data/raw_data/finance_report/*.md`
- `data/dealed_data/*`（.md/.json/.html）

**文档数量**：`data/` 下约 **105 个 .md 文件**（含重复路径），去重后约 60+ 独立文档。

**Chunk 数量**：由 `build_vector_index.py` 决定，chunk_size=500、overlap=50，每个文档按字符切块。运行 `python -m scripts.build_vector_index` 后，`pipeline.collection.count()` 为实际 chunk 数。

---

## 5. Prompt 设计

### 5.1 资产问答（market）system prompt

**代码位置**：`prompts.yaml` 第 125-152 行（generator.system_prompt 全文）

核心约束（节选）：
```
1. 结论先行：走势概述第一句必须是判断性结论
2. 专业术语：自然使用"回踩支撑位"、"放量突破"等
3. 数据嵌入叙事：把价位、日期、成交量融入叙述
4. 主动推理：事件归因必须给出具体因素，禁止"无法确定"
5. 核心规则：所有数据来自【实时数据】部分，绝不编造；绝不预测未来走势、绝不给出买卖建议
6. 严禁使用："无法确定"、"信息有限"、"未明确指出"等空话
```

### 5.2 RAG 问答（knowledge）system prompt

同一 generator system_prompt，user_template 按 `route_type` 分支（`prompts.yaml` L226-236）：

```
【参考知识】{{rag_context}}
请按四段结构回答：定义、计算公式/核心区别、实际应用举例、注意事项
```

### 5.3 不同 QueryType 的 prompt 模板

**有**。`render_user_prompt("generator", route_type=...)` 根据 `route_type` 渲染不同 user_template：

- `market`：L161-179
- `news` / `hybrid`：L181-224
- `knowledge`：L226-236
- `else`：L238-252

**代码位置**：`backend/app/agent/core.py` 第 847 行附近，`route_type` 来自 `route.query_type.value`。

---

## 6. 数据源 Fallback

### 6.1 MarketDataService 优先级

**get_price**（`backend/app/market/service.py` L535-598）：
1. Redis 缓存
2. Finnhub
3. Stooq
4. Alpha Vantage
5. yfinance

**get_history**（L599-630）：
1. Redis 缓存
2. Stooq
3. Alpha Vantage
4. yfinance

（Finnhub 的 candle 需付费，故 history 不用 Finnhub）

### 6.2 Redis 缓存 Key 与 TTL

**代码位置**：`backend/app/config.py` L44-46，`backend/app/market/service.py` L541-543, L602-604

| Key 格式 | TTL | 说明 |
|----------|-----|------|
| `price:{symbol}` | CACHE_TTL_PRICE = **60** 秒 | 实时价格 |
| `history:{symbol}:{range_key or days}` | CACHE_TTL_HISTORY = **86400**（24h） | 历史行情 |
| 公司信息 | CACHE_TTL_INFO = **604800**（7天） | 若有单独缓存 |

---

## 7. 前端渲染

### 7.1 SSE 事件推送顺序

**代码位置**：`backend/app/agent/core.py` 第 782-985 行

1. `model_selected`
2. `tool_start`（每个工具）
3. `tool_data`（每个工具返回）
4. **`blocks`**（`_compose_answer` 完成后，L834-835）
5. `chunk`（无 LLM 时的 template_text）或 `analysis_chunk`（LLM 流式，L904）
6. `done`

**blocks 与 analysis_chunk 先后**：**blocks 先于 analysis_chunk**。blocks 在工具执行、校验、编排完成后立即推送；analysis_chunk 在 `ResponseGenerator.generate_stream()` 流式输出时推送。

### 7.2 图表组件

**库**：**Recharts**（`frontend/package.json` L14: `"recharts": "^2.10.3"`）

**组件**：`frontend/src/components/Chart.jsx`，使用 `AreaChart`、`LineChart`（`recharts`）

**支持**：
- `chartType="history"`：单资产价格面积图
- `chartType="comparison"`：多资产归一化折线图
- 时间范围切换（1m/3m/6m/ytd/1y/5y）

### 7.3 「参考来源·知识库摘录」展示逻辑

**数据来源**：
- 后端 `_compose_answer` 在 `search_knowledge` 有文档时，创建 `type="quote"` 的 StructuredBlock（`core.py` L663-670）
- `data` 含 `items`（id, source, score, preview, method）、`text`、`method_used`
- `done` 事件中的 `rag_citations` 来自 `search_knowledge` 的 documents（L960-970）

**前端渲染**：
- `ThreeZoneLayout` 将 `type="quote"` 的 blocks 作为 `refBlocks`（L19）
- `ResponseBlocks` → `ReferenceSource` 组件（`ChatComponents.jsx` L201）
- `ReferenceSource`（`ReferenceSource.jsx`）展示折叠区「📚 参考来源」，展开后显示 items：source、相关度、method（向量+重排/关键词匹配）、preview
- `SourcesPanel` 展示 `sources` + `rag_citations`，显示「数据来源：xxx · N 条引用」

---

## 8. 技术选型理由

**代码注释/文档**：主要见 `README.md` 第二节「技术选型说明」。

| 选型 | 理由（README） |
|------|----------------|
| **DeepSeek vs GPT-4** | 成本约 GPT-4 的 1/10，中文能力强，OpenAI 兼容，金融术语与合规拒答表现稳定（L191） |
| **ChromaDB** | 轻量、可本地持久化、Python 原生、无额外服务，与 sentence-transformers 集成好（L203） |
| **规则路由 vs LLM 分类** | 规则保证行情类 100% 走 API；LLM 路由延迟高、有误判，且无 LLM 时无法降级（L189） |
| **BGE-base-zh** | 中文金融语料表现好，768 维在精度与速度间平衡，对「市盈率」「市净率」等术语语义捕捉优于通用模型（L204） |

---

## 附录：关键文件索引

| 模块 | 文件 | 关键行 |
|------|------|--------|
| 路由 | `app/routing/router.py` | 14-257 |
| 工具编排 | `app/agent/core.py` | 264-301, 741-985 |
| 校验 | `app/analysis/validator.py` | 16-139 |
| ResponseGuard | `app/agent/core.py` | 30-56 |
| RAG | `app/rag/pipeline.py` | 184-346 |
| Prompt | `prompts.yaml` | 35-252 |
| 行情 | `app/market/service.py` | 535-630 |
| 配置 | `app/config.py` | 44-60 |
| 前端 SSE | `frontend/src/App.jsx` | 145-194 |
| 图表 | `frontend/src/components/Chart.jsx` | 1-190 |
| 参考来源 | `frontend/src/components/Chat/ReferenceSource.jsx` | 1-126 |
