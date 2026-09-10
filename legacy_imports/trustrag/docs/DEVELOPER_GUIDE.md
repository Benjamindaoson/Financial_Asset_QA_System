# TrustRAG Developer Guide / 开发者指南

## Table of Contents / 目录

- [Introduction / 简介](#introduction)
- [Architecture Overview / 架构概览](#architecture-overview)
- [Module Structure / 模块结构](#module-structure)
- [Development Setup / 开发环境设置](#development-setup)
- [Common Development Tasks / 常见开发任务](#common-development-tasks)
- [Deployment Guide / 部署指南](#deployment-guide)
- [Maintenance & Troubleshooting / 维护与故障排除](#maintenance--troubleshooting)
- [FAQ / 常见问题](#faq)

---

## Introduction / 简介

TrustRAG is an industrial-grade financial RAG (Retrieval-Augmented Generation) system designed for high-precision evidence extraction with full traceability and evidence constraints.

TrustRAG 是一个工业级金融 RAG（检索增强生成）系统，专为高精度证据提取而设计，具有完整的可追溯性和零幻觉保证。

### Key Features / 核心特性

- **Evidence-Based Answers**: All answers are backed by verifiable evidence from ingested documents
- **evidence-constrained generation**: LLM only renders verified bindings, never generates new numbers
- **Full Traceability**: Every answer links back to source documents, pages, and evidence IDs
- **Risk-Aware Arbitration**: Multi-source conflict detection and resolution
- **Multi-Tenant Support**: Data isolation and access control
- **Performance Monitoring**: Built-in metrics and performance tracking
- **Audit Logging**: Complete operation and decision traceability

---

## Architecture Overview / 架构概览

### System Layers / 系统分层

```
┌─────────────────────────────────────────┐
│         API Layer (FastAPI)             │
│  - Query Endpoints                       │
│  - Ingestion Endpoints                   │
│  - Health & Stats                        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Core System (TrustRAG)             │
│  - Query Processing                      │
│  - Route Planning                        │
│  - Fast Path (Canonical Facts)          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    Engine Layer                          │
│  ┌──────────────┐  ┌──────────────┐    │
│  │  Retrieval   │  │  Generation  │    │
│  │  Pipeline    │  │  Prompts     │    │
│  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐                       │
│  │  Ingestion   │                       │
│  │  Pipeline    │                       │
│  └──────────────┘                       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    Judgment & Validation                 │
│  - Evidence Arbitration                  │
│  - Post-Binding Verification             │
│  - Risk Assessment                       │
└─────────────────────────────────────────┘
```

### Data Flow / 数据流

1. **Query Input** → Query Profiling → Route Planning
2. **Fast Path Check** → Canonical Fact Store (if applicable)
3. **Evidence Retrieval** → Multi-tier retrieval (micro/base/macro)
4. **Evidence Selection** → Quality filtering and ranking
5. **Arbitration** → Conflict detection and resolution
6. **Answer Generation** → LLM rendering from verified bindings
7. **Verification** → Post-binding validation
8. **Result** → SystemResult with full traceability

---

## Module Structure / 模块结构

### Core Modules / 核心模块

#### `trust_rag/core/`

- **`system.py`**: Main system entry point, orchestrates all components
- **`executor.py`**: Progressive execution with staged upgrades
- **`profile.py`**: Query profiling and intent detection
- **`routing.py`**: Route planning and budget allocation
- **`exceptions.py`**: Unified exception handling framework
- **`tenant.py`**: Multi-tenant support and data isolation
- **`monitoring.py`**: Performance monitoring and metrics
- **`audit_log.py`**: Audit logging and decision traceability
- **`scenario_templates.py`**: High-risk scenario configurations

#### `trust_rag/core/judgment/`

- **`orchestrator.py`**: Evidence arbitration orchestrator
- **`guards.py`**: Pre-judgment gates and validation
- **`validation.py`**: Post-binding verification
- **`verdict.py`**: Verdict and judgment models

#### `trust_rag/engine/`

- **`retrieval/`**: Retrieval pipeline, adapters, evidence selection
- **`ingest/`**: Document ingestion pipeline, parsers, chunkers
- **`generation/`**: Answer generation prompts

#### `trust_rag/api/`

- **`main.py`**: FastAPI application and endpoints

#### `trust_rag/cli/`

- **`query.py`**: CLI query interface
- **`ingest.py`**: CLI ingestion interface

---

## Development Setup / 开发环境设置

### Prerequisites / 前置要求

- Python 3.10+
- Node.js 18+ (for UI)
- pip / npm

### Installation / 安装

```bash
# Clone repository
git clone <repository-url>
cd trust_rag

# Install Python dependencies
pip install -r requirements.txt

# Install UI dependencies
cd trust_rag/ui
npm install
```

### Environment Configuration / 环境配置

Create `.env` file:

```bash
# Environment
TRUSTRAG_ENV=dev  # dev, test, prod

# API Configuration
TRUSTRAG_API_HOST=0.0.0.0
TRUSTRAG_API_PORT=8000

# Optional: Config file path
TRUSTRAG_CONFIG=config_dev.json
```

### Running Development Server / 运行开发服务器

```bash
# Backend API
cd trust_rag
python -m trust_rag.api.main

# Or using uvicorn directly
uvicorn trust_rag.api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend UI (in another terminal)
cd trust_rag/ui
npm run dev
```

---

## Common Development Tasks / 常见开发任务

### Adding a New Parser / 添加新解析器

1. Create parser in `trust_rag/engine/ingest/parsers/`
2. Implement `parse()` method returning `IngestResult`
3. Register in `trust_rag/engine/ingest/router.py`

Example:

```python
from trust_rag.engine.ingest.parsers.base import BaseParser

class MyParser(BaseParser):
    def parse(self, file_path: str) -> IngestResult:
        # Implementation
        pass
```

### Adding a New Retrieval Strategy / 添加新检索策略

1. Extend `RetrievalAdapter` in `trust_rag/engine/retrieval/adapter.py`
2. Implement search methods
3. Register in route planning

### Adding a New Scenario Template / 添加新场景模板

1. Add scenario type to `ScenarioType` enum in `scenario_templates.py`
2. Define configuration in `SCENARIO_TEMPLATES`
3. Apply via `ScenarioManager.apply_scenario()`

### Customizing Error Handling / 自定义错误处理

All exceptions should inherit from `TrustRAGException`:

```python
from trust_rag.core.exceptions import TrustRAGException, ErrorCategory, ErrorSeverity

class MyCustomException(TrustRAGException):
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
```

---

## Deployment Guide / 部署指南

### Production Deployment / 生产部署

#### Using Docker / 使用 Docker

```bash
# Build image
docker build -t trustrag:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/artifacts:/app/artifacts \
  -v $(pwd)/logs:/app/logs \
  -e TRUSTRAG_ENV=prod \
  trustrag:latest
```

#### Using Docker Compose / 使用 Docker Compose

```bash
docker-compose up -d
```

### Configuration Management / 配置管理

1. Create environment-specific config files:
   - `config_dev.json`
   - `config_test.json`
   - `config_prod.json`

2. Set `TRUSTRAG_ENV` environment variable

3. Config hot-reload is enabled by default (no restart needed)

### Monitoring Setup / 监控设置

Performance metrics are automatically logged to `logs/metrics/`

Access metrics:

```python
from trust_rag.core.monitoring import get_monitor

monitor = get_monitor()
report = monitor.get_performance_report()
```

### Multi-Tenant Setup / 多租户设置

Enable in `config.py`:

```python
multi_tenant:
  enabled: true
  default_tenant_id: "default"
  enforce_isolation: true
```

Use tenant context:

```python
from trust_rag.core.tenant import TenantContext

with TenantContext(tenant_id="tenant_123"):
    result = rag.process_query("...")
```

---

## Maintenance & Troubleshooting / 维护与故障排除

### Common Issues / 常见问题

#### Index Not Loading / 索引未加载

**Symptoms**: No results returned, empty index stats

**Solutions**:
1. Check ingestion directory: `artifacts/ingestion/`
2. Verify chunks.jsonl files exist
3. Run index refresh: `POST /api/ingest/refresh`
4. Check logs for errors

#### High Memory Usage / 内存使用过高

**Symptoms**: System slowdown, OOM errors

**Solutions**:
1. Check performance monitor: `monitor.get_system_metrics_summary()`
2. Reduce batch ingestion size
3. Enable chunk size limits
4. Monitor with `psutil` metrics

#### Slow Query Processing / 查询处理缓慢

**Symptoms**: Queries taking >5 seconds

**Solutions**:
1. Check retrieval budget settings
2. Review route planning configuration
3. Enable fast path for common queries
4. Optimize index structure

### Logging / 日志

Logs are stored in:
- Application logs: `logs/`
- Audit logs: `logs/audit/`
- Performance metrics: `logs/metrics/`

Log levels:
- `DEBUG`: Detailed debugging information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error conditions
- `CRITICAL`: Critical failures

### Backup & Recovery / 备份与恢复

**Backup**:
- Artifacts: `artifacts/` directory
- Config: `config_*.json` files
- Logs: `logs/` directory (optional)

**Recovery**:
1. Restore artifacts directory
2. Restore config files
3. Run index refresh
4. Verify system health

---

## FAQ / 常见问题

### Q: How do I add support for a new document format? / 如何添加新文档格式支持？

A: Create a new parser in `trust_rag/engine/ingest/parsers/` and register it in the router.

### Q: How to customize confidence thresholds? / 如何自定义置信度阈值？

A: Modify `query_thresholds.confidence_threshold` in config or use scenario templates.

### Q: How to enable multi-tenant mode? / 如何启用多租户模式？

A: Set `multi_tenant.enabled = true` in config and use `TenantContext` for operations.

### Q: How to export audit logs? / 如何导出审计日志？

A: Use `AuditLogger.export_logs()` method or query via API.

### Q: How to monitor system performance? / 如何监控系统性能？

A: Use `PerformanceMonitor` API or check metrics in `logs/metrics/`.

### Q: How to handle large file ingestion? / 如何处理大文件摄入？

A: Use batch ingestion with size limits, or enable auto-sync for incremental processing.

### Q: How to customize refusal reasons? / 如何自定义拒绝原因？

A: Modify `JudgmentOrchestrator` to add custom refusal logic and reasons.

### Q: How to add new risk flags? / 如何添加新风险标志？

A: Extend risk flag detection in evidence selection and arbitration logic.

---

## Additional Resources / 其他资源

- [API Reference](./API_REFERENCE.md)
- [Design Overview](./DESIGN_OVERVIEW.md)
- [Architecture Documentation](./ARCHITECTURE.md)
- [System Design Principles](./SYSTEM_DESIGN_PRINCIPLES.md)
- [Failure Modes](./FAILURE_MODES.md)

---

**Last Updated**: 2025-01-XX
**Version**: 1.0



