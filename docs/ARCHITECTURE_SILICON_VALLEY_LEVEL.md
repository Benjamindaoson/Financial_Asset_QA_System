# Financial Asset QA System — 硅谷级 LLM 架构说明

> 本文档基于全代码遍历，整合系统介绍与架构说明，供 CTO/CEO 演示及技术评审使用。

---

## 一、系统介绍内容来源索引

| 来源 | 路径 | 内容摘要 |
|------|------|----------|
| README | `README.md` | 项目定位、设计理念、架构图、技术选型、数据来源、部署说明 |
| 逐字稿 | `docs/3分钟演示视频逐字稿.md` | 演示脚本、话术清单 |
| 本文档 | `docs/ARCHITECTURE_SILICON_VALLEY_LEVEL.md` | 硅谷级架构说明 |
| API 文档 | `docs/API_QUICK_REFERENCE.md` | API 快速参考 |
| 系统状态 | `SYSTEM_STATUS.md` | 组件状态与测试记录 |
| 产品路线图 | `PRODUCT_ROADMAP.md` | 演进规划 |

---

## 二、硅谷级架构说明（How to Explain Your Architecture）

### 2.1 一句话定位（Elevator Pitch）

> **A deterministic, multi-stage LLM pipeline for financial QA that enforces data provenance and blocks investment advice at the routing layer.**

> 一个**确定性多阶段 LLM 流水线**，用于金融问答，在路由层强制数据溯源并拦截投资建议。

---

### 2.2 核心架构原则（Architectural Principles）

| 原则 | 英文表述 | 实现 |
|------|----------|------|
| **数据溯源** | Data provenance over model creativity | 行情必走 API，LLM 不参与数值计算 |
| **显式流水线** | Explicit DAG over black-box agents | 5 阶段：接入 → 编排 → 执行 → 校验 → 合成 |
| **双重反幻觉** | Dual anti-hallucination (input + output) | DataValidator + ResponseGuard |
| **渐进式渲染** | Progressive rendering (data-first) | blocks 早于 chunk 推送，图表秒现 |
| **降级保护** | Graceful degradation | LLM 不可用时输出 blocks + 原文，前端不白屏 |

---

### 2.3 分层架构（Layered Architecture）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLIENT (React + SSE)                                                        │
│  - Consumes SSE events: model_selected → tool_start/tool_data → blocks →    │
│    chunk/analysis_chunk → done                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  GATEWAY (FastAPI + sse-starlette)                                           │
│  - POST /api/chat → QueryEnricher.enrich() → AgentCore.run() → SSE stream   │
│  - GET /health, /models, /chart/{symbol}                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION (AgentCore, app/agent/core.py)                                │
│  - QueryRouter.classify_async() → _build_tool_plan() → _execute_tools_parallel()│
│  - DataValidator → TechnicalAnalyzer → _compose_answer() → ResponseGenerator │
│  - ResponseGuard.validate()                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
│  EXECUTION LAYER      │ │  EXECUTION LAYER       │ │  EXECUTION LAYER      │
│  MarketDataService    │ │  HybridRAGPipeline      │ │  WebSearchService     │
│  (get_price,          │ │  (search_knowledge)    │ │  SECFilingsService    │
│   get_history, etc.)  │ │  Token-match fast path │ │  (search_web,         │
│  Finnhub→Stooq→AV→yf  │ │  Vector+BM25+RRF+Rerank│ │   search_sec)         │
└───────────────────────┘ └───────────────────────┘ └───────────────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                                  │
│  - Redis (price 60s, history 24h, info 7d)                                   │
│  - ChromaDB (BGE-base-zh, BM25, RRF)                                        │
│  - External: Finnhub, Stooq, Alpha Vantage, yfinance, Tavily, SEC EDGAR    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 2.4 请求生命周期（Request Lifecycle）— 12 步

| 步骤 | 组件 | 动作 |
|------|------|------|
| 1 | `QueryEnricher` | 预处理 query（hints、别名） |
| 2 | `QueryRouter.classify_async()` | 规则路由：关键词 + 实体提取（`QueryEnricher.extract_symbols` + `TickerMapper.normalize`） |
| 3 | 路由决策 | `refuses_advice` → 直接拒答；否则得到 `QueryRoute`（type, symbols, requires_*） |
| 4 | `_build_tool_plan()` | 根据 route 编排工具列表（无 LLM，纯规则） |
| 5 | `_execute_tools_parallel()` | 并发执行工具，推送 `tool_start` / `tool_data` |
| 6 | `DataValidator.validate_tool_results()` | 校验完整性，计算 confidence |
| 7 | `DataValidator.should_block_response()` | 不满足最低要求 → 推送 warning + done，提前结束 |
| 8 | `TechnicalAnalyzer.analyze()` | 若 `get_history` ≥20 条，计算 RSI、MACD、布林带、支撑/压力位 |
| 9 | `_compose_answer()` | 编排 `StructuredBlock`（chart/table/bullets/warning/quote/news/key_metrics/analysis） |
| 10 | 推送 `blocks` | 前端秒级渲染图表/表格 |
| 11 | `ResponseGenerator.generate_stream()` | 基于 `_build_llm_context()` 注入的 api_data/rag/news，流式生成分析文本 |
| 12 | `ResponseGuard.validate()` | 校验 LLM 输出中的数值是否均来自 tool payload → 推送 `done` |

---

### 2.5 工具清单（Tool Inventory）

| 工具 | 数据源 | 用途 |
|------|--------|------|
| `get_price` | Finnhub → Stooq → Alpha Vantage → yfinance | 实时报价 |
| `get_history` | Stooq → Alpha Vantage → yfinance | 历史 OHLCV |
| `get_change` | 基于 get_history 计算 | 涨跌幅 |
| `get_info` | Alpha Vantage / yfinance | 公司/资产信息 |
| `get_metrics` | 基于 get_history 计算 | 波动率、收益、最大回撤、RSI |
| `compare_assets` | 并发 get_price/get_metrics/get_history | 多资产对比 |
| `search_knowledge` | HybridRAGPipeline | 知识库检索 |
| `search_web` | Tavily API | 新闻搜索 |
| `search_sec` | SEC EDGAR API | 财报检索 |

---

### 2.6 RAG 检索链路（Hybrid Retrieval Pipeline）

```
用户 query
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Fast Path: token-match (_search_local_documents)               │
│  - 无模型、低延迟，基于 token 重叠                               │
│  - 若有结果 → 直接返回，跳过向量+rerank                          │
└─────────────────────────────────────────────────────────────────┘
    │ 若 token-match 为空且 ChromaDB 可用
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  search_grounded() (HybridRAGPipeline)                           │
│  1. 向量检索 Top-K=20 (BGE-base-zh, ChromaDB cosine)             │
│  2. BM25 检索 Top-K=20 (jieba 分词)                             │
│  3. RRF 融合 (k=60): score = sum(1/(k+rank))                     │
│  4. BGE-reranker 精排 Top-N=3                                   │
└─────────────────────────────────────────────────────────────────┘
    │ 若仍无结果且配置 Tavily
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Supplemental web search (Tavily)                               │
└─────────────────────────────────────────────────────────────────┘
```

**代码位置**：`app/rag/hybrid_pipeline.py`（HybridRAGPipeline）、`app/rag/pipeline.py`（RAGPipeline、token-match）

---

### 2.7 SSE 事件类型（Event Schema）

| 事件 | 触发时机 | 用途 |
|------|----------|------|
| `model_selected` | 启动时 | 告知前端模型与复杂度 |
| `tool_start` | 每个工具开始执行 | 显示 loading 状态 |
| `tool_data` | 每个工具返回 | 可选展示中间数据 |
| `blocks` | `_compose_answer` 完成后 | **核心**：图表/表格/新闻卡片，前端秒级渲染 |
| `chunk` | 模板文本（无 LLM 时） | 简单摘要 |
| `analysis_chunk` | LLM 流式输出 | 打字机效果的分析文本 |
| `done` | 全流程完成 | 置信度、sources、disclaimer |
| `error` | 异常 | 错误信息 |

**StructuredBlock 类型**：`chart`、`key_metrics`、`table`、`quote`、`news`、`bullets`、`warning`、`analysis`

---

### 2.8 反幻觉机制（Anti-Hallucination）

| 层级 | 机制 | 代码位置 |
|------|------|----------|
| **路由** | `refuses_advice`：检测「买入/推荐/目标价」→ 直接拒答 | `QueryRouter` |
| **输入** | `DataValidator`：校验工具返回是否满足最低要求（如无价格则拒答） | `app/analysis/validator.py` |
| **Prompt** | `hard_guardrails`：禁止预测、推测、投资建议 | `PromptManager` |
| **输出** | `ResponseGuard`：校验 LLM 输出中的数值是否均来自 tool payload | `app/agent/core.py` |

---

### 2.9 与 LangChain / Agent 的对比（Why Not Agent Framework）

| 维度 | 本系统 | LangChain / Agent |
|------|--------|-------------------|
| **控制流** | 显式 DAG，规则驱动 | 黑盒，LLM 驱动 |
| **数据流** | 行情必走 API，可审计 | 依赖 LLM 选择工具，无法保证 |
| **数值计算** | 后端计算，LLM 不参与 | 易让 LLM 参与计算，易幻觉 |
| **降级** | 每阶段可独立降级 | 框架抽象过重，降级困难 |
| **合规** | 路由层前置拦截 | 需额外中间件 |

---

### 2.10 硅谷级话术模板（Pitch Script for CTO/CEO）

**开场（30 秒）**  
> "We built a **deterministic multi-stage pipeline** for financial QA. The key design choice: we **reject black-box agents**. Every number comes from an API or our knowledge base—the LLM only synthesizes text. We have **dual anti-hallucination**: DataValidator at input, ResponseGuard at output. Investment advice is blocked at the routing layer before any tool runs."

**架构亮点（1 分钟）**  
> "Five explicit stages: Gateway → Orchestration → Execution → Validation → Synthesis. The orchestration layer uses **rule-based routing**—no LLM for tool selection in the critical path. Market data tools always hit real APIs with a three-level fallback: Finnhub, Stooq, Alpha Vantage. RAG uses **vector + BM25 + RRF fusion** with a token-match fast path for low latency. We push **blocks** (charts, tables) before the LLM finishes—progressive rendering, data-first UX."

**合规与风险（30 秒）**  
> "We never let the LLM compute numbers. We never let it recommend buys or sells. The router detects advice-seeking queries and refuses before execution. All numeric claims in the LLM output are validated against tool payloads. If the LLM is down, we still serve blocks and raw data—graceful degradation."

---

## 三、代码索引（Code Reference）

| 模块 | 路径 | 核心类/函数 |
|------|------|-------------|
| Agent 核心 | `app/agent/core.py` | `AgentCore`, `ResponseGuard`, `run()`, `_build_tool_plan()`, `_compose_answer()` |
| 路由 | `app/routing/router.py` | `QueryRouter`, `QueryType`, `QueryRoute` |
| 实体提取 | `app/enricher/enricher.py` | `QueryEnricher.extract_symbols()` |
| RAG | `app/rag/hybrid_pipeline.py` | `HybridRAGPipeline` |
| RAG 基类 | `app/rag/pipeline.py` | `RAGPipeline`, `_search_local_documents()` |
| 行情 | `app/market/service.py` | `MarketDataService`, `TickerMapper` |
| 校验 | `app/analysis/validator.py` | `DataValidator` |
| 技术分析 | `app/analysis/technical.py` | `TechnicalAnalyzer` |
| 合成 | `app/core/response_generator.py` | `ResponseGenerator.generate_stream()` |
| API | `app/api/routes.py` | `POST /chat`, `GET /health` |
| 模型 | `app/models/schemas.py` | `SSEEvent`, `StructuredBlock`, `ToolResult` |

---

## 四、总结

本系统采用 **Deterministic Pipeline over Black-Box Agent** 的架构范式，通过显式阶段、规则路由、双重反幻觉和渐进式渲染，在金融场景下实现**数据可追溯、合规可审计、降级可预期**。适合作为硅谷级 LLM 架构评审的参考文档。
