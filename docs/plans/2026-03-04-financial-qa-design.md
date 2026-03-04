# Financial Asset QA System - Design Document

**Date:** 2026-03-04
**Version:** 1.0
**Status:** Design Approved

---

## Executive Summary

This document describes the design of a **Financial Asset QA System** - a production-grade AI application that combines real-time market data, knowledge retrieval (RAG), and web search to answer financial questions with accuracy and transparency.

**Core Principle:**
> LLM should not generate financial facts. LLM should explain verified financial data.

**System Capabilities:**
1. Real-time asset price queries and trend analysis
2. Financial knowledge Q&A (RAG-based)
3. Event-driven market analysis (news integration)
4. Multi-source reasoning with source attribution

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
│  React + Vite + TailwindCSS (Port 5173)                     │
│  - Chat Interface                                            │
│  - Streaming Response Display                                │
│  - Price Charts & Visualizations                             │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP/WebSocket
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend API Layer                       │
│  FastAPI (Port 8000)                                        │
│  - REST endpoints (/api/chat, /api/health)                 │
│  - WebSocket for streaming responses                        │
│  - Request validation & error handling                      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Query Router Layer                        │
│  - Rule-based classification (fast path)                    │
│  - LLM-based classification (fallback)                      │
│  - Query type: MARKET / KNOWLEDGE / NEWS / HYBRID           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangChain Agent Core                      │
│  - OpenAI GPT-4 as reasoning engine                        │
│  - Tool selection & orchestration                           │
│  - Response synthesis with guardrails                       │
│  - Conversation memory                                       │
└────┬────────────┬────────────┬─────────────────────────────┘
     │            │            │
     ▼            ▼            ▼
┌─────────┐ ┌──────────┐ ┌────────────┐
│ Market  │ │   RAG    │ │ Web Search │
│  Data   │ │  Tool    │ │   Tool     │
│  Tool   │ │          │ │            │
└────┬────┘ └────┬─────┘ └─────┬──────┘
     │           │              │
     ▼           ▼              ▼
┌─────────┐ ┌──────────┐ ┌────────────┐
│yfinance │ │ChromaDB  │ │ Tavily/    │
│   API   │ │+ OpenAI  │ │ SerpAPI    │
│         │ │Embeddings│ │            │
└─────────┘ └──────────┘ └────────────┘
```

### 1.2 Technology Stack

**Frontend:**
- React 18 + Vite
- TailwindCSS for styling
- Recharts for data visualization
- WebSocket for streaming

**Backend:**
- Python 3.11+
- FastAPI for API server
- LangChain for agent orchestration
- OpenAI GPT-4 for reasoning

**Data Layer:**
- ChromaDB for vector storage
- Redis for caching (5min TTL)
- yfinance for market data

**Infrastructure:**
- Docker Compose for deployment
- Prometheus + Grafana for monitoring
- Structured logging (JSON format)

---

## 2. Core Modules

### 2.1 Query Router

**Purpose:** Classify user queries to optimize tool selection and reduce agent reasoning complexity.

**Classification Strategy:**
1. **Rule-based (Fast Path)** - 70%+ queries
   - Keyword matching: 股价, 价格, 涨跌
   - Ticker symbol detection: BABA, TSLA
   - Pattern matching for common queries

2. **LLM-based (Fallback)** - Ambiguous queries
   - GPT-3.5-turbo for classification
   - Confidence score threshold: 0.7
   - Multi-label support for hybrid queries

**Query Types:**
- `MARKET`: Stock prices, trends, historical data
- `KNOWLEDGE`: Financial concepts, definitions
- `NEWS`: Recent events, news analysis
- `HYBRID`: Requires multiple data sources

**Benefits:**
- Reduced latency (rule-based is instant)
- Lower cost (fewer GPT-4 calls)
- Better tool selection accuracy

### 2.2 Market Data Tool

**Input Schema:**
```python
{
  "ticker": str,           # BABA, TSLA, or 阿里巴巴
  "period": str,           # 1d, 7d, 1mo, 3mo
  "metrics": List[str]     # ["price", "change_pct", "volume"]
}
```

**Processing Pipeline:**
1. Ticker normalization (阿里巴巴 → BABA)
2. Cache check (Redis, 5min TTL)
3. API call (yfinance) with timeout (10s)
4. Data validation & calculation
5. Cache update

**Output Schema:**
```python
{
  "ticker": "BABA",
  "current_price": 85.32,
  "period_change": -3.18,
  "period_change_pct": -3.61,
  "trend": "下跌",
  "high": 88.50,
  "low": 84.20,
  "data_source": "yfinance",
  "timestamp": "2026-03-04T10:30:00Z"
}
```

**Guardrails:**
- Price must be > 0
- Change percentage: -50% to +50%
- Timestamp within 24 hours
- Required fields validation

### 2.3 RAG Tool

**Knowledge Base Structure:**
```
knowledge_base/
├── financial_concepts/      # 市盈率, 市净率, ROE
├── financial_statements/    # 收入, 净利润, 现金流
├── market_basics/           # 股票, 债券, 基金
└── company_profiles/        # 公司基本信息
```

**Processing Pipeline:**
1. Query embedding (OpenAI text-embedding-3-small)
2. Vector search (ChromaDB, top_k=3)
3. Relevance filtering (threshold=0.7)
4. Optional reranking (cross-encoder)
5. Context assembly with metadata

**Output Schema:**
```python
{
  "documents": [
    {
      "content": "市盈率是...",
      "source": "financial_concepts/valuation_metrics.md",
      "relevance_score": 0.89,
      "category": "valuation_metrics"
    }
  ],
  "total_found": 3
}
```

**Enhancements:**
- Structured knowledge with metadata filtering
- Reranker for improved relevance
- Source attribution for transparency

### 2.4 Web Search Tool

**Input Schema:**
```python
{
  "query": str,              # Search keywords
  "ticker": str,             # Optional, for context
  "date_range": str,         # 1d, 7d, 30d
  "max_results": int         # Default: 5
}
```

**Processing Pipeline:**
1. Query enhancement (add ticker + date context)
2. API call (Tavily/SerpAPI)
3. Result filtering (relevance + date)
4. Content extraction & summarization
5. Source credibility ranking

**Source Credibility Tiers:**
- **Tier 1**: Reuters, Bloomberg, WSJ
- **Tier 2**: CNBC, Yahoo Finance, MarketWatch
- **Tier 3**: Blogs, forums (lower weight)

**Output Schema:**
```python
{
  "results": [
    {
      "title": "阿里巴巴Q4财报超预期",
      "snippet": "阿里巴巴发布...",
      "url": "https://...",
      "published_date": "2026-01-15",
      "source": "Reuters",
      "credibility_tier": 1
    }
  ],
  "total_results": 5,
  "search_query": "BABA 阿里巴巴 1月15日"
}
```

---

## 3. Agent Design

### 3.1 Agent Architecture

**Components:**
- **Planner**: Analyzes query and decides tool execution strategy
- **Executor**: Invokes tools and handles errors
- **Tool Registry**: Manages available tools and their schemas
- **Guardrails**: Validates outputs and prevents hallucination

### 3.2 System Prompt (Layered Design)

**Layer 1: Role & Responsibility**
```
你是一个专业的金融资产分析助手。
核心职责：
1. 基于可靠数据源回答金融问题
2. 区分"客观数据"与"分析性描述"
3. 明确标注信息来源
4. 不预测未来走势
```

**Layer 2: Data Handling Principles**
```
核心原则：
- 永远不要编造金融数据
- 必须使用工具获取实时数据
- 数据来源必须明确标注
- 不确定时明确告知用户

数据分类：
• 客观数据 → market_data_tool
• 金融知识 → rag_tool
• 市场事件 → web_search_tool
```

**Layer 3: Response Format (Fixed Schema)**
```markdown
### Market Data
- Current Price: $XX.XX
- Period Change: ±X.XX%
- Trend: 上涨/下跌/震荡

### Analysis
[Data-driven interpretation]

### Sources
- Market Data: Yahoo Finance
- News: Reuters, Bloomberg
- Updated: 2026-03-04 10:30 UTC
```

**Layer 4: Guardrails**
```
禁止行为：
✗ 预测未来股价
✗ 提供投资建议
✗ 编造数据或新闻
✗ 使用过时数据而不标注

不确定时：
"根据当前可获取的数据..."
"需要注意的是，该信息可能不完整..."
```

### 3.3 Response Synthesis

**Principles:**
1. **Facts vs Interpretation** - Clearly separate objective data from analysis
2. **Source Attribution** - Always cite data sources with timestamps
3. **Structured Output** - Use fixed markdown schema for consistency
4. **Uncertainty Handling** - Explicitly state when information is incomplete

---

## 4. Data Flow

**Example: "阿里巴巴最近7天涨跌情况如何？"**

```
1. User Query → Frontend (WebSocket)
2. API Layer → Validate & Route
3. Query Router → Classify as MARKET type
4. Agent Planner → Select market_data_tool
5. Tool Executor → Call market_data_tool(ticker="BABA", period="7d")
6. Market Service → Check Redis cache
7. Cache Miss → yfinance API call
8. Data Validation → Guardrails check
9. Cache Update → Store in Redis (5min TTL)
10. Agent Synthesis → Generate structured response
11. Streaming → Send chunks via WebSocket
12. Frontend → Render markdown + charts
13. Audit Log → Record tool call + output
```

---

## 5. Production Considerations

### 5.1 Caching Strategy

**Redis Cache:**
- Key format: `market:{ticker}:{period}`
- TTL: 5 minutes for real-time data
- Cache warming for popular tickers (AAPL, TSLA, BABA)

### 5.2 Error Handling

**Timeout & Retry:**
- API timeout: 10 seconds
- Retry: 2 attempts with exponential backoff
- Fallback: Return partial data with error flag

**Graceful Degradation:**
- If market API fails → Use cached data + warning
- If RAG fails → Use LLM knowledge + disclaimer
- If web search fails → Skip news section

### 5.3 Observability

**Metrics (Prometheus):**
- Tool call latency (p50, p95, p99)
- Tool success/failure rates
- Token usage per query
- Cache hit rate

**Tracing (OpenTelemetry):**
- End-to-end query tracing
- Tool execution spans
- LLM call latency

**Logging (Structured JSON):**
- Query classification results
- Tool inputs/outputs
- Agent reasoning steps
- Error stack traces

### 5.4 Cost Monitoring

**Token Usage Tracking:**
- GPT-4 tokens per query
- Embedding tokens for RAG
- Daily/monthly cost estimates

**Optimization:**
- Use GPT-3.5 for classification
- Cache embeddings
- Limit context window size

### 5.5 Audit & Compliance

**Audit Logs:**
- `tool_calls.log`: All tool invocations with timestamps
- `data_sources.log`: Data source attribution
- `model_outputs.log`: LLM responses for review

**Retention Policy:**
- Audit logs: 90 days
- User queries: 30 days (anonymized)
- System metrics: 1 year

---

## 6. Evaluation Framework

### 6.1 Test Datasets

**Market Queries (50 samples):**
- Simple price queries: "BABA当前股价"
- Trend analysis: "特斯拉最近7天走势"
- Multi-asset: "比较BABA和TSLA"

**Knowledge Queries (30 samples):**
- Definitions: "什么是市盈率"
- Calculations: "如何计算ROE"
- Comparisons: "收入和净利润的区别"

**Hybrid Queries (20 samples):**
- Event analysis: "为何阿里巴巴1月15日大涨"
- Comprehensive: "特斯拉近期走势及原因"

### 6.2 Evaluation Metrics

**Accuracy:**
- Data correctness (vs ground truth)
- Source attribution accuracy
- Calculation correctness

**Quality:**
- Response completeness
- Clarity and structure
- Hallucination rate (< 5%)

**Performance:**
- Latency (p95 < 5s)
- Tool selection accuracy (> 90%)
- Cache hit rate (> 60%)

### 6.3 Continuous Evaluation

**Automated Tests:**
- Daily regression tests on test datasets
- Tool accuracy validation
- Response format validation

**Human Review:**
- Weekly sample review (20 queries)
- Hallucination detection
- User feedback analysis

---

## 7. Project Structure (Production-Grade)

```
Financial_Asset_QA_System/
├── frontend/                  # React + Vite
├── backend/
│   ├── api/                   # FastAPI endpoints
│   ├── agent/                 # Planner + Executor + Registry
│   ├── routing/               # Query classifier + Policy engine
│   ├── tools/                 # Market + RAG + Web Search
│   ├── services/              # Data access layer
│   └── models/                # Schemas & types
├── vectorstore/               # ChromaDB storage
├── data/                      # Knowledge base
├── infra/                     # Redis + Monitoring + Logging
├── eval/                      # Evaluation framework
├── audit/                     # Audit logs
├── policies/                  # AI governance
├── scripts/                   # Utilities
├── docker/                    # Containerization
└── docs/                      # Documentation
```

---

## 8. Future Enhancements

### 8.1 LLMOps Layer
- Prompt versioning & registry
- A/B testing framework
- Experiment tracking (MLflow)

### 8.2 Advanced Features
- Multi-asset comparison
- Portfolio analysis
- Technical indicators (MA, RSI)
- Sentiment analysis

### 8.3 Scalability
- Horizontal scaling (multiple agent instances)
- External vector DB (Pinecone/Qdrant)
- Feature store for ML models

---

## 9. Success Criteria

**Functional:**
- ✓ Accurate market data retrieval
- ✓ Relevant knowledge retrieval (RAG)
- ✓ Event-driven analysis with news
- ✓ Multi-source reasoning

**Non-Functional:**
- ✓ Latency p95 < 5 seconds
- ✓ Hallucination rate < 5%
- ✓ Tool selection accuracy > 90%
- ✓ System uptime > 99%

**User Experience:**
- ✓ Clear, structured responses
- ✓ Source attribution
- ✓ Streaming for better UX
- ✓ Professional financial tone

---

## 10. Conclusion

This design represents a **production-grade AI system** that balances:
- **Accuracy**: Facts from reliable tools, not LLM generation
- **Transparency**: Clear source attribution
- **Performance**: Caching, routing optimization
- **Governance**: Audit logs, guardrails, evaluation

The system follows the core principle:
> **LLM should not generate financial facts. LLM should explain verified financial data.**

This architecture is suitable for:
- Prototype/demo systems (current scope)
- Production deployment (with infra enhancements)
- Future ML/feature store integration

---

**Document Status:** Ready for Implementation Planning
**Next Step:** Invoke `writing-plans` skill to create detailed implementation plan
