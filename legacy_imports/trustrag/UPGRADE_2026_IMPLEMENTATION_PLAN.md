# TrustRAG 2.0 生产级升级实施计划

## 📋 升级概述

本次升级将TrustRAG从"MVP概念验证"提升为"硅谷生产级AI系统"，解决4个核心架构缺陷：

1. **存储层**: JSON文件系统 → PostgreSQL + pgvector
2. **检索层**: all-MiniLM-L6-v2 → BGE-M3 + BGE-Reranker
3. **解析层**: Tesseract → Qwen2-VL VLM
4. **队列层**: 自研Redis → Celery + RabbitMQ

## 🎯 升级目标

- **可靠性**: 99.9% SLA，ACID事务支持
- **性能**: 检索召回率提升至90%+，响应时间<500ms
- **可观测性**: 完整的分布式追踪和监控
- **可维护性**: 专业级任务队列和错误处理

---

## 📅 实施时间表 (12周)

### **阶段一：稳固底座与数据治理 (第1-4周)**

#### **核心目标**: 解决存储瓶颈，建立自动化评价体系，确保"GA铁律"不回滚

#### **1. 双轨存储迁移 (第1-2周)**
#### **任务**:

1. **数据库迁移** (3天)
   ```bash
   # 1. 安装PostgreSQL + pgvector
   sudo apt-get install postgresql postgresql-contrib
   # 启用pgvector扩展
   psql -d trust_rag -c "CREATE EXTENSION vector;"

   # 2. 创建数据库和用户
   createdb trust_rag
   createuser trust_rag_user --createdb --login
   psql -c "ALTER USER trust_rag_user PASSWORD 'secure_password';"

   # 3. 运行迁移脚本
   python scripts/migrate_to_postgres.py
   ```

2. **消息队列部署** (2天)
   ```bash
   # 安装RabbitMQ
   sudo apt-get install rabbitmq-server
   sudo systemctl enable rabbitmq-server

   # 配置用户和权限
   sudo rabbitmqctl add_user trust_rag secure_password
   sudo rabbitmqctl add_vhost trust_rag_vhost
   sudo rabbitmqctl set_permissions -p trust_rag_vhost trust_rag ".*" ".*" ".*"
   ```

3. **监控栈部署** (2天)
   ```bash
   # OpenTelemetry Collector
   docker run -d --name otel-collector \
     -p 4317:4317 \
     -v $(pwd)/otel-config.yaml:/etc/otel/config.yaml \
     otel/opentelemetry-collector

   # Prometheus + Grafana (可选)
   docker-compose up -d prometheus grafana
   ```

#### **验收标准**:
- ✅ PostgreSQL + pgvector 正常运行
- ✅ RabbitMQ 队列可正常收发消息
- ✅ OTLP collector 可接收遥测数据

---

### **第3-6周: 核心组件升级 (集成分层路由解析)**

#### **核心创新: 分层路由解析 (降低60% Token成本)**
```python
# 智能路由解析器 - 根据文档复杂度选择最优策略
from trust_rag.engine.ingest.parsers.tiered_parser import TieredDocumentParser

class SmartIngestionPipeline:
    def __init__(self):
        # 分层路由解析器
        self.parser = TieredDocumentParser()

        # 路径A (80%流量): 轻量级解析
        # - PyMuPDF + Marker (零成本)
        # - 适用于标准文本文档

        # 路径B (20%流量): VLM增强解析
        # - Qwen2-VL (高精度)
        # - 适用于复杂表格/图表文档

    def parse_document(self, file_path: str):
        # 自动复杂度分析 + 智能路由
        profile = self.parser.profiler.analyze_document(file_path)
        logger.info(f"路由决策: {profile.tier} (成本:${profile.estimated_cost})")

        return self.parser.parse_document(file_path)
```

#### **目标**: 逐个升级核心组件，保持系统稳定

1. **存储层升级** (Phase 1 - 4天)
   ```python
   # 在 system.py 中集成新存储层
   from trust_rag.engine.retrieval.vector_store import PostgreSQLVectorStore

   class TrustRAG:
       def __init__(self):
           # 初始化新向量存储
           self.vector_store = PostgreSQLVectorStore()
           # 保持向后兼容的FAISS索引作为缓存层
           self.faiss_cache = FAISSCache()  # 降级使用
   ```

2. **检索层升级** (Phase 2 - 5天)
   ```python
   # 替换嵌入模型
   from trust_rag.engine.retrieval.embedding_v2 import BGEEmbeddingEngine

   class RetrievalAdapter:
       def __init__(self):
           self.embedding = BGEEmbeddingEngine()
           self.reranker = BGEReranker()
   ```

3. **解析层升级** (Phase 3 - 3天)
   ```python
   # 在 IngestionPipeline 中集成VLM
   from trust_rag.engine.ingest.parsers.vlm_parser import QwenVLDocumentParser

   class IngestPipeline:
       def __init__(self):
           self.vlm_parser = QwenVLDocumentParser()
           self.ocr_parser = TesseractOCRParser()  # 降级fallback
   ```

#### **验收标准**:
- ✅ 新旧存储层并存运行
- ✅ BGE-M3嵌入质量 > all-MiniLM-L6-v2
- ✅ VLM解析准确率 > 85%

---

### **第6-8周: 分布式系统迁移**

#### **目标**: 迁移到专业分布式架构

1. **任务队列迁移** (5天)
   ```python
   # 在 system.py 中集成Celery
   from trust_rag.runtime.dispatcher.celery_queue import TrustRAGCelery

   class TrustRAG:
       def __init__(self):
           self.task_queue = TrustRAGCelery()
           # 保持旧Redis队列作为降级选项
           self.redis_queue = RedisTaskQueue()  # 降级使用
   ```

2. **异步任务定义** (3天)
   ```python
   # 创建 celery_tasks.py
   from trust_rag.runtime.dispatcher.celery_queue import get_celery_app

   @get_celery_app().celery_app.task(name='trust_rag.tasks.ingest_document')
   def ingest_document_task(file_path: str, doc_id: str):
       # 异步文档摄入逻辑
       pass

   @get_celery_app().celery_app.task(name='trust_rag.tasks.retrieval_query')
   def retrieval_query_task(query: str, plan: dict):
       # 异步检索逻辑
       pass
   ```

#### **验收标准**:
- ✅ Celery worker 可正常启动和处理任务
- ✅ 任务监控面板可访问
- ✅ 异步处理延迟 < 2秒

---

### **第9-10周: 观测性集成 + 影子仲裁**

#### **目标**: 实现全链路可观测性 + 平滑灰度发布

#### **核心创新: 影子仲裁机制 (零风险算法升级)**
```python
# 影子仲裁器 - 新旧算法并行对比
from trust_rag.core.judgment.shadow_arbitrator import ShadowArbitrator

class GradualRolloutSystem:
    def __init__(self):
        # 初始化新旧仲裁器
        self.legacy_arbitrator = LegacyJudgmentOrchestrator()
        self.new_arbitrator = NewJudgmentOrchestrator()  # 2026版

        # 影子仲裁器
        self.arbitrator = ShadowArbitrator(
            legacy_arbitrator=self.legacy_arbitrator,
            new_arbitrator=self.new_arbitrator,
            mode=ArbitrationMode.SHADOW_MODE  # 初始影子模式
        )

    def gradual_rollout(self):
        # Phase 1: 影子模式 (新算法并行，不影响用户)
        self.arbitrator.switch_mode(ArbitrationMode.SHADOW_MODE)

        # Phase 2: 金丝雀模式 (5%流量使用新算法)
        if self.arbitrator.get_stats()["quality"]["quality_ok"]:
            self.arbitrator.switch_mode(ArbitrationMode.CANARY_MODE)

        # Phase 3: 逐步放量 (基于性能指标自动调整)
        if self._check_rollout_readiness():
            self.arbitrator.switch_mode(ArbitrationMode.GRADUAL_ROLLOUT)

        # Phase 4: 完全切换
        if self._all_metrics_green():
            self.arbitrator.switch_mode(ArbitrationMode.FULL_NEW)
```

1. **分布式追踪集成** (3天)
   ```python
   # 在 system.py 中集成追踪
   from trust_rag.core.observability.tracing import get_tracer

   class TrustRAG:
       def __init__(self):
           self.tracer = get_tracer()

       def process_query(self, query: str):
           with self.tracer.trace_query(query):
               # 查询处理逻辑
               pass
   ```

2. **LangSmith集成** (2天)
   ```python
   # 为LLM操作添加追踪
   from trust_rag.core.observability.tracing import trace_generation

   def generate_answer(self, query: str, bindings: dict):
       with trace_generation(query, "gpt-4", max_tokens=1000):
           response = self.llm.generate(query, bindings)
           return response
   ```

#### **验收标准**:
- ✅ Jaeger/Grafana 可视化追踪数据
- ✅ LangSmith 显示LLM调用和成本
- ✅ 错误率和延迟指标正常

---

### **第11-12周: 生产上线准备**

#### **目标**: 完整生产环境验证

1. **性能基准测试** (3天)
   ```bash
   # 运行全面性能测试
   python tests/perf/test_upgrade_benchmarks.py

   # 对比新旧版本指标:
   # - 检索召回率
   # - 查询响应时间
   # - 系统资源使用
   # - 错误率
   ```

2. **生产配置优化** (2天)
   ```yaml
   # production_config.yaml
   database:
     max_connections: 100
     connection_timeout: 30

   task_queue:
     worker_prefetch_multiplier: 1
     worker_max_tasks_per_child: 1000

   observability:
     trace_sampling_rate: 0.1  # 生产环境采样率
     enable_langsmith: true
   ```

3. **降级策略验证** (2天)
   ```python
   # 确保所有组件都有降级策略
   class SystemWithFallbacks:
       def __init__(self):
           self.primary_store = PostgreSQLVectorStore()
           self.fallback_store = FAISSVectorStore()  # 降级

           self.primary_queue = TrustRAGCelery()
           self.fallback_queue = RedisTaskQueue()   # 降级
   ```

#### **验收标准**:
- ✅ 性能基准测试通过
- ✅ 降级策略有效
- ✅ 生产配置稳定

---

## 🔧 具体实施步骤详解

### **1. 存储层迁移脚本**
```python
# scripts/migrate_to_postgres.py
import json
from pathlib import Path
from trust_rag.engine.retrieval.vector_store import PostgreSQLVectorStore
from trust_rag.engine.retrieval.embedding_v2 import BGEEmbeddingEngine

def migrate_existing_data():
    """迁移现有JSONL数据到PostgreSQL"""
    vector_store = PostgreSQLVectorStore()
    embedding_engine = BGEEmbeddingEngine()

    # 扫描现有ingestion目录
    ingestion_dir = Path("artifacts/ingestion")
    for doc_dir in ingestion_dir.iterdir():
        chunks_file = doc_dir / "chunks.jsonl"
        if chunks_file.exists():
            print(f"Migrating {doc_dir.name}...")

            chunks = []
            with open(chunks_file, 'r') as f:
                for line in f:
                    chunk = json.loads(line.strip())
                    chunks.append(chunk)

            # 重新计算嵌入 (用新模型)
            texts = [chunk['text'] for chunk in chunks]
            embeddings = embedding_engine.encode_dense(texts)

            # 批量插入PostgreSQL
            vector_chunks = []
            for chunk, embedding in zip(chunks, embeddings):
                vector_chunks.append(VectorChunk(
                    chunk_id=chunk['chunk_id'],
                    doc_id=chunk.get('doc_id', doc_dir.name),
                    text=chunk['text'],
                    embedding=embedding.tolist(),
                    metadata=chunk.get('metadata', {}),
                    modality=chunk.get('modality', 'text_native'),
                    page_number=chunk.get('page_number', 0),
                    chunk_index=chunk.get('chunk_index', 0)
                ))

            vector_store.insert_chunks(vector_chunks)
            print(f"Migrated {len(chunks)} chunks for {doc_dir.name}")

if __name__ == "__main__":
    migrate_existing_data()
```

### **2. 渐进式部署策略**
```python
# system.py - 支持新旧组件并存
class TrustRAG:
    def __init__(self):
        # 新组件 (2026)
        self.vector_store = PostgreSQLVectorStore()
        self.embedding = BGEEmbeddingEngine()
        self.task_queue = TrustRAGCelery()

        # 旧组件 (降级使用)
        self.faiss_cache = FAISSVectorStore()  # 缓存层
        self.old_embedding = SentenceTransformer('all-MiniLM-L6-v2')
        self.redis_queue = RedisTaskQueue()   # 降级队列

    def process_query(self, query: str):
        try:
            # 优先使用新组件
            return self._process_with_new_stack(query)
        except Exception as e:
            logger.warning(f"New stack failed, falling back: {e}")
            # 降级到旧组件
            return self._process_with_old_stack(query)
```

### **3. 监控面板配置**
```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "15672:15672"  # Management UI

  flower:
    image: mher/flower
    environment:
      - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
    ports:
      - "5555:5555"

  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
```

---

## 🎯 风险评估与缓解策略

### **高风险项目**:

1. **数据迁移风险** ⚠️⚠️⚠️
   - **风险**: 数TB数据迁移可能失败
   - **缓解**: 先小批量测试，再全量迁移；保留完整备份

2. **性能下降风险** ⚠️⚠️
   - **风险**: 新模型计算量更大
   - **缓解**: 实施缓存策略；监控性能指标；准备回滚计划

3. **依赖复杂性风险** ⚠️⚠️
   - **风险**: 新增PostgreSQL/RabbitMQ/OTel等依赖
   - **缓解**: 使用Docker容器化；编写详细部署文档

### **回滚策略**:
```python
# system.py 回滚支持
class TrustRAGWithRollback:
    def __init__(self, use_new_stack: bool = True):
        self.use_new_stack = use_new_stack

        if use_new_stack:
            # 2026 组件
            self.store = PostgreSQLVectorStore()
        else:
            # 2023 组件 (回滚)
            self.store = JSONFileStore()

    def rollback_to_legacy(self):
        """一键回滚到旧架构"""
        self.use_new_stack = False
        logger.info("Rolled back to legacy stack")
```

---

## 📊 成功指标

### **功能指标**:
- ✅ **检索质量**: Recall@5 > 85% (当前~70%)
- ✅ **响应时间**: P95 < 500ms (当前~800ms)
- ✅ **解析准确率**: 表格识别 > 90% (当前~50%)

### **可靠性指标**:
- ✅ **可用性**: 99.9% uptime
- ✅ **数据持久性**: ACID事务保证
- ✅ **可观测性**: 100% 请求可追踪

### **运维指标**:
- ✅ **部署时间**: < 30分钟
- ✅ **监控覆盖**: 100% 关键组件
- ✅ **故障恢复**: < 5分钟

---

## 🔄 与用户方案的对比分析

### **用户方案的优秀创新点** ✅

#### **1. 分层路由解析 (核心突破)**
- **用户方案**: 80%轻量级解析(零成本) + 20% VLM解析(高精度)
- **我的改进**: 实现了`TieredDocumentParser` + 复杂度预检
- **优势**: 降低60% Token成本，性能与质量并重

#### **2. 影子仲裁机制 (零风险发布)**
- **用户方案**: 新旧算法并行，数据驱动的灰度发布
- **我的实现**: `ShadowArbitrator`类，支持5种发布模式
- **优势**: 基于性能指标的自动放量，质量门禁

#### **3. 稳固底座优先 (务实路线)**
- **用户方案**: 先解决审计问题，再进行技术升级
- **我的调整**: 增加了第1-2周的基础设施准备阶段

### **核心指标对比表**

| 维度 | 当前 (MVP) | 用户方案目标 | 我的方案目标 | 达成策略 |
|------|-----------|-------------|-------------|----------|
| **存储** | JSON + FAISS | PostgreSQL (ACID保证) | PostgreSQL + 双轨并存 | 双轨迁移，零停机 |
| **解析** | 文本为主 (Tesseract) | 视觉原生 (VLM + 逻辑路由) | 分层路由 (80%轻量级 + 20% VLM) | 复杂度预检 + 智能路由 |
| **Token成本** | 高 (全量调用) | 降低60% (分层解析+缓存) | 降低60% (路径A零成本) | 80%文档走轻量级路径 |
| **P95延迟** | 不稳定 | < 500ms (同步路径优化) | < 500ms (HNSW索引) | PostgreSQL优化 + 缓存 |
| **部署保障** | 人工点测 | CI/CD自动化门禁 | CI/CD + 影子仲裁 | Golden Set回归测试 |

### **方案融合优势** 🎯

通过整合用户方案的优秀思路，我的升级计划现在具备：

1. **成本效益最优**: 分层路由解析确保80%文档零成本解析
2. **发布安全性**: 影子仲裁机制实现零风险的算法升级
3. **运维友好**: 双轨存储 + 自动化门禁 + 可观测性
4. **渐进可控**: 每个阶段都有独立的验收标准和回滚策略

这个融合方案既保持了技术先进性，又具备了生产可行性，是真正能在2026年落地的TrustRAG升级路线图。

---

## 🎉 升级完成后的系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    TrustRAG 2.0 (2026)                      │
├─────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)                                        │
│  ├── Health Checks                                          │
│  ├── Rate Limiting                                          │
│  └── Request Tracing                                        │
├─────────────────────────────────────────────────────────────┤
│  Application Layer                                          │
│  ├── Query Processing (with distributed tracing)           │
│  ├── Evidence Arbitration                                   │
│  └── Answer Generation (with LangSmith)                    │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                              │
│  ├── Vector Store (PostgreSQL + pgvector)                  │
│  ├── Embedding Service (BGE-M3)                            │
│  ├── Reranker Service (BGE-Reranker-v2)                    │
│  ├── VLM Parser (Qwen2-VL)                                 │
│  └── Task Queue (Celery + RabbitMQ)                        │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                       │
│  ├── PostgreSQL (ACID + vector search)                      │
│  ├── RabbitMQ (message queue)                               │
│  ├── Redis (result backend)                                 │
│  └── OpenTelemetry (observability)                          │
├─────────────────────────────────────────────────────────────┤
│  Monitoring & Observability                                 │
│  ├── Jaeger (distributed tracing)                           │
│  ├── Prometheus (metrics)                                   │
│  ├── Grafana (dashboards)                                   │
│  ├── Flower (Celery monitoring)                             │
│  └── LangSmith (LLM observability)                          │
└─────────────────────────────────────────────────────────────┘
```

这个12周的升级计划将把TrustRAG从概念验证系统提升为真正的企业级生产系统，每一步都有详细的技术实现和风险控制策略。
