# TrustRAG Design Overview / 设计概览

## Table of Contents / 目录

- [System Architecture / 系统架构](#system-architecture)
- [Core Components / 核心组件](#core-components)
- [Data Flow / 数据流](#data-flow)
- [Layered Architecture / 分层架构](#layered-architecture)
- [Exception Handling / 异常处理](#exception-handling)
- [Audit & Logging / 审计与日志](#audit--logging)
- [Performance Mechanisms / 性能机制](#performance-mechanisms)
- [Multi-Tenant Design / 多租户设计](#multi-tenant-design)
- [Configuration Management / 配置管理](#configuration-management)

---

## System Architecture / 系统架构

### High-Level Overview / 高层概览

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                           │
│  (Web UI, CLI, API Clients)                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                              │
│  FastAPI Endpoints                                          │
│  - /api/query                                               │
│  - /api/ingest                                              │
│  - /api/stats                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Core System Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Query      │  │   Route      │  │   Fast       │    │
│  │   Profiler   │  │   Planner    │  │   Path       │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Judgment   │  │   Evidence   │  │   Post-Bind  │    │
│  │   Orchestrator│ │   Selector    │  │   Verifier   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Engine Layer                             │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  Retrieval      │         │  Ingestion       │         │
│  │  Pipeline        │         │  Pipeline        │         │
│  │  - Adapter       │         │  - Parsers       │         │
│  │  - Scorer        │         │  - Chunkers      │         │
│  │  - Reranker      │         │  - Validators    │         │
│  └──────────────────┘         └──────────────────┘         │
│                                                              │
│  ┌──────────────────┐                                       │
│  │  Generation      │                                       │
│  │  - Prompts       │                                       │
│  │  - Renderer      │                                       │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  - Index (Chunks)                                           │
│  - Canonical Fact Store                                      │
│  - Audit Logs                                                │
│  - Performance Metrics                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components / 核心组件

### 1. Query Processing Flow / 查询处理流程

```
User Query
    ↓
Pre-Judgment Gate (Scope Check)
    ↓
Query Profiling (Intent Detection)
    ↓
Route Planning (Budget Allocation)
    ↓
Fast Path Check (Canonical Facts)
    ├─→ Hit: Return immediately
    └─→ Miss: Continue
    ↓
Evidence Retrieval (Multi-tier)
    ├─→ Micro Tier (Atomic facts)
    ├─→ Base Tier (Paragraphs)
    └─→ Macro Tier (Sections)
    ↓
Evidence Selection & Ranking
    ↓
Judgment Arbitration
    ├─→ Conflict Detection
    ├─→ Risk Assessment
    └─→ Decision Making
    ↓
Answer Generation (LLM Rendering)
    ↓
Post-Binding Verification
    ↓
SystemResult (with full traceability)
```

### 2. Ingestion Flow / 摄入流程

```
Document Input
    ↓
Preflight Validation
    ├─→ Quality Check
    ├─→ Format Detection
    └─→ Language Detection
    ↓
Parser Selection (Router)
    ↓
Document Parsing
    ├─→ Text Extraction
    ├─→ Table Extraction
    ├─→ Chart Extraction
    └─→ Metadata Extraction
    ↓
Chunking (MCU Strategy)
    ├─→ Micro Chunks (Atomic)
    ├─→ Base Chunks (Composite)
    └─→ Macro Chunks (Summary)
    ↓
Quality Gate
    ↓
Index Storage
    ↓
IngestResult
```

---

## Data Flow / 数据流

### Query Processing Data Flow / 查询处理数据流

```
┌─────────────┐
│   Query     │
└──────┬──────┘
       │
       ↓
┌─────────────────┐      ┌──────────────┐
│ Query Profiler  │─────→│ QueryProfile │
└─────────────────┘      └──────┬───────┘
                                │
                                ↓
┌─────────────────┐      ┌──────────────┐
│ Route Planner   │─────→│  RoutePlan    │
└─────────────────┘      └──────┬───────┘
                                │
                                ↓
┌─────────────────┐      ┌──────────────┐
│ Retrieval       │─────→│ ScoredChunks │
│ Pipeline        │      └──────┬───────┘
└─────────────────┘             │
                                ↓
┌─────────────────┐      ┌──────────────┐
│ Evidence        │─────→│ Selected      │
│ Selector        │      │ Evidence     │
└─────────────────┘      └──────┬───────┘
                                │
                                ↓
┌─────────────────┐      ┌──────────────┐
│ Judgment        │─────→│ Arbitrated    │
│ Orchestrator    │      │ Verdict       │
└─────────────────┘      └──────┬───────┘
                                │
                                ↓
┌─────────────────┐      ┌──────────────┐
│ Answer          │─────→│ SystemResult  │
│ Generator       │      └──────────────┘
└─────────────────┘
```

---

## Layered Architecture / 分层架构

### Layer Responsibilities / 层级职责

#### 1. API Layer / API 层
- **Responsibility**: HTTP request/response handling, validation
- **Components**: FastAPI endpoints, request models, error handlers
- **Isolation**: No business logic, only orchestration

#### 2. Core System Layer / 核心系统层
- **Responsibility**: Query orchestration, decision making
- **Components**: TrustRAG system, profilers, planners, orchestrators
- **Isolation**: Independent of storage and retrieval implementation

#### 3. Engine Layer / 引擎层
- **Responsibility**: Domain-specific processing (retrieval, ingestion, generation)
- **Components**: Pipelines, adapters, parsers, chunkers
- **Isolation**: Pluggable implementations

#### 4. Data Layer / 数据层
- **Responsibility**: Data persistence and retrieval
- **Components**: Index storage, fact store, audit logs
- **Isolation**: Abstract storage interface

### Decoupling Principles / 解耦原则

1. **Interface-Based Design**: Components communicate via interfaces
2. **Dependency Injection**: Dependencies injected, not hard-coded
3. **Event-Driven**: Asynchronous operations where possible
4. **Configuration-Driven**: Behavior controlled by configuration

---

## Exception Handling / 异常处理

### Exception Hierarchy / 异常层次结构

```
TrustRAGException (Base)
├── IngestionException
│   ├── IngestionFailedException
│   └── DataFormatException
├── RetrievalException
│   ├── EntityMatchException
│   ├── MetricMatchException
│   └── PeriodMatchException
├── JudgmentException
│   └── RefusalException
├── ValidationException
├── ConfigException
├── PermissionException
└── IndexCorruptedException
```

### Error Flow / 错误流程

```
Exception Raised
    ↓
Catch & Wrap (if needed)
    ↓
Log with Context
    ├─→ Error Category
    ├─→ Severity Level
    ├─→ Trace ID
    └─→ Technical Details
    ↓
User-Friendly Message
    ↓
SystemResult with Error Info
    ↓
API Response
```

### Error Context / 错误上下文

Every exception includes:
- **Trace ID**: For correlation
- **User Message**: Friendly error message
- **Technical Details**: Debug information
- **Recovery Suggestion**: Actionable advice
- **Stack Trace**: For critical errors

---

## Audit & Logging / 审计与日志

### Audit Log Structure / 审计日志结构

```json
{
  "timestamp": "2025-01-XX...",
  "operation_type": "query",
  "user_id": "user_123",
  "tenant_id": "tenant_456",
  "trace_id": "tr_1704067200000",
  "operation_details": {
    "query": "...",
    "risk_level": "medium"
  },
  "decision_type": "verified",
  "decision_reason": "...",
  "evidence_ids": ["ev_1", "ev_2"],
  "sources_used": ["doc_1", "doc_2"],
  "duration_ms": 234,
  "error": null
}
```

### Logging Levels / 日志级别

- **DEBUG**: Detailed debugging information
- **INFO**: General operational information
- **WARNING**: Warning conditions
- **ERROR**: Error conditions
- **CRITICAL**: Critical failures

### Audit Log Locations / 审计日志位置

- Application logs: `logs/`
- Audit logs: `logs/audit/audit_YYYYMMDD.jsonl`
- Performance metrics: `logs/metrics/metrics_YYYYMMDD_HHMMSS.json`

---

## Performance Mechanisms / 性能机制

### Performance Monitoring / 性能监控

```
Operation Start
    ↓
Record Start Time
    ↓
Execute Operation
    ↓
Record End Time
    ↓
Calculate Duration
    ↓
Record System Metrics
    ├─→ CPU Usage
    ├─→ Memory Usage
    └─→ Disk Usage
    ↓
Update Statistics
    ↓
Generate Report (if needed)
```

### Performance Metrics / 性能指标

- **Operation Metrics**: Duration, success rate, error rate
- **System Metrics**: CPU, memory, disk usage
- **Throughput**: Operations per second
- **Latency**: P50, P95, P99 percentiles

### Optimization Strategies / 优化策略

1. **Fast Path**: Canonical fact store for common queries
2. **Caching**: Cache frequent queries and results
3. **Parallel Processing**: Concurrent retrieval from multiple tiers
4. **Progressive Upgrade**: Start with cheap operations, upgrade if needed
5. **Budget Management**: Limit resource usage per query

---

## Multi-Tenant Design / 多租户设计

### Data Isolation / 数据隔离

```
┌─────────────────────────────────────┐
│  Tenant Context                     │
│  tenant_id: "tenant_123"           │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  Data Operations                    │
│  - Filter by tenant_id              │
│  - Validate tenant access           │
│  - Enforce isolation                │
└─────────────────────────────────────┘
```

### Tenant Context Flow / 租户上下文流程

```
Request with tenant_id
    ↓
Set Tenant Context (ContextVar)
    ↓
All Operations
    ├─→ Filter by tenant_id
    ├─→ Validate access
    └─→ Enforce isolation
    ↓
Clear Tenant Context
```

### Isolation Levels / 隔离级别

1. **Strict Isolation**: All data isolated by tenant
2. **Shared Resources**: Some resources shared (e.g., fact store)
3. **No Isolation**: Multi-tenant disabled

---

## Configuration Management / 配置管理

### Configuration Structure / 配置结构

```
TrustRAGConfig
├── Paths
├── Query Budget
├── Query Thresholds
├── Scoring Weights
├── Feature Flags
├── Ingest Config
├── Multi-Tenant Config
└── API Config
```

### Configuration Sources / 配置来源

1. **Default Values**: Hard-coded defaults
2. **Config Files**: `config_{env}.json`
3. **Environment Variables**: `TRUSTRAG_*`
4. **Runtime Updates**: Hot reload from files

### Hot Reload Flow / 热加载流程

```
Config File Modified
    ↓
Detect Change (File Watcher)
    ↓
Reload Configuration
    ↓
Validate Configuration
    ↓
Apply to System
    ↓
No Restart Required
```

---

## Sequence Diagrams / 时序图

### Query Processing Sequence / 查询处理时序

```
User          API          System        Retrieval    Judgment
 │             │             │              │            │
 │──Query─────→│             │              │            │
 │             │──Process──→│              │            │
 │             │             │──Retrieve───→│            │
 │             │             │←─Candidates──│            │
 │             │             │──Arbitrate───────────────→│
 │             │             │←──Verdict─────────────────│
 │             │             │──Generate──→│            │
 │             │             │←─Answer────│            │
 │             │←─Result──────│              │            │
 │←─Response───│             │              │            │
```

### Ingestion Sequence / 摄入时序

```
User          API          Pipeline      Parser      Index
 │             │             │             │          │
 │──Upload────→│             │             │          │
 │             │──Ingest────→│             │          │
 │             │             │──Parse─────→│          │
 │             │             │←─Content────│          │
 │             │             │──Chunk─────→│          │
 │             │             │←─Chunks────│          │
 │             │             │──Store─────────────────→│
 │             │             │←─Success────────────────│
 │             │←─Result──────│             │          │
 │←─Response───│             │             │          │
```

---

## Design Principles / 设计原则

### 1. Isolation / 隔离
- **Cognitive Isolation**: LLM never sees raw data for extraction
- **Data Isolation**: Multi-tenant data separation
- **Component Isolation**: Loose coupling between modules

### 2. Determinism / 确定性
- **Deterministic Fast Path**: Identical results for same inputs
- **Reproducible Results**: Same query → same result
- **No Randomness**: Predictable behavior

### 3. Traceability / 可追溯性
- **Full Evidence Chain**: Every answer linked to sources
- **Complete Audit Trail**: All operations logged
- **Decision Transparency**: Clear reasoning for all decisions

### 4. Fail-Safe / 故障安全
- **Default Refusal**: Refuse rather than hallucinate
- **Graceful Degradation**: Continue with reduced functionality
- **Error Recovery**: Automatic retry and fallback

---

**Last Updated**: 2025-01-XX
**Version**: 1.0



