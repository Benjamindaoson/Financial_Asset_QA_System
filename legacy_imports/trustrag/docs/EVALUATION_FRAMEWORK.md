# TrustRAG 自动评估指标体系 + 可执行评估框架

## 概述

完整的评估框架，支持一键运行评估并生成 JSON+HTML 报告，覆盖所有关键指标。

## 已完成的交付物

### A. 指标数据模型 ✅

**文件**: `trust_rag/eval/schema.py`

定义了完整的评估数据模型：
- `EvalReport`: 完整评估报告
- `RunMeta`: 运行元数据
- `StageLatency`: 阶段延迟指标（p50/p95/p99）
- `CostMetrics`: 成本和资源使用指标
- `RetrievalMetrics`: 检索质量指标（recall/mrr/ndcg）
- `IngestMetrics`: 摄入质量指标
- `TrustMetrics`: 信任和安全指标
- `RobustnessMetrics`: 鲁棒性指标
- `Scorecard`: 综合评分卡（含红线规则）

### B. 指标采集与埋点 ✅

**文件**: `trust_rag/eval/instrumentation.py`

- 在 system.py 主链路写入 stage spans：
  - `pre_judgment`: 预判断门
  - `profile`: 查询分析
  - `route_plan`: 路由规划
  - `fast_path`: 快速路径检查
  - `retrieve`: 证据检索
  - `judge`: 仲裁判断
  - `generate`: 答案生成
  - `verify`: 后置验证
- 采集每次请求的端到端延迟，聚合 p50/p95/p99
- 对接现有 monitoring.py 输出 CPU/MEM/DISK 使用统计

### C. 评估数据集与判分器 ✅

**文件**: 
- `trust_rag/eval/datasets/golden_v1.jsonl`: 黄金标准数据集
- `trust_rag/eval/judges.py`: 判分器实现

**判分器**:
- `ExactMatchJudge`: 精确匹配判断
- `NumericErrorJudge`: 数值误差判断
- `EvidenceSupportJudge`: 证据支持判断
- `RefusalJudge`: 拒绝正确性判断
- `VerificationJudge`: 验证有效性判断
- `CompositeJudge`: 复合判分器

### D. 检索评估 ✅

**文件**: `trust_rag/eval/retrieval_eval.py`

计算指标：
- `recall_at_k`: Recall@1, Recall@5, Recall@10
- `mrr_at_k`: MRR@5, MRR@10
- `ndcg_at_k`: NDCG@5, NDCG@10
- `calculate_rerank_gain`: 重排序增益

### E. 压测与极端用例指标化 ✅

**文件**: `tests/perf/test_extreme_cases.py` (已修改)

- 每个测试输出标准化结果（耗时、资源、成功率、失败原因）
- 评估框架可读取其输出并写入 `EvalReport.robustness_metrics`
- 报告归档到 `artifacts/perf_reports/`

### F. 成本评估 ✅

**文件**: `trust_rag/eval/cost.py`

统计指标：
- Token 使用（如启用LLM）
- CPU 时间（ms）
- 内存峰值（MB）
- 磁盘 I/O（MB）
- 索引大小（MB）
- 派生指标：`cost_per_query`, `cost_per_page` 等

### G. 统一执行入口与报告生成 ✅

**文件**: 
- `trust_rag/eval/run.py`: 执行入口
- `trust_rag/eval/report_html.py`: HTML 报告生成

**使用方式**:
```bash
# 运行核心评估
python -m trust_rag.eval.run --suite core --dataset golden_v1

# 运行完整评估（包含压测）
python -m trust_rag.eval.run --suite full --dataset golden_v1
```

**输出**:
- `artifacts/eval_reports/{date}/{commit}/report.json`
- `artifacts/eval_reports/{date}/{commit}/report.html`

### H. CI 集成 ✅

**文件**: `tests/eval/test_eval_smoke.py`

- 跑一个最小 golden 集并确保 report 生成成功
- 确保在无外部依赖环境下可运行

## 报告内容

### 必须包含的指标

✅ **延迟指标**:
- p50/p95/p99 延迟
- 各阶段延迟分解

✅ **吞吐指标**:
- QPS（每秒查询数）
- 并发测试摘要

✅ **成本/资源**:
- Token 成本（USD）
- CPU/内存/磁盘使用
- 每查询成本

✅ **准确率**:
- 精确匹配率（EM）
- 数值误差率
- 整体准确率

✅ **检索指标**:
- Recall@k
- MRR@k
- NDCG@k
- Rerank 增益

✅ **拒答精度/召回**:
- 拒绝精确度
- 拒绝召回率
- 拒绝 F1

✅ **证据支撑率**:
- 有证据查询比例
- 平均证据数量

✅ **后置验证通过率**:
- 验证检查次数
- 验证通过率

✅ **极端用例通过率**:
- 超长文档测试
- 批量大文件测试
- 特殊格式测试
- 并发查询测试

## 红线规则

评估框架自动检查以下红线规则：

1. **高风险误答 > 0**: 如果存在高风险误答，标记为 FAIL
2. **Unsupported Claims > 0**: 如果存在不支持的主张，标记为 FAIL
3. **P95 延迟超阈值**: 如果 P95 延迟超过 5000ms，标记为 FAIL

违反任何红线规则：
- `scorecard.status` 设为 "FAIL"
- 返回非 0 退出码
- 在报告中明确标注失败原因

## 使用示例

### 基本使用

```bash
# 运行评估
python -m trust_rag.eval.run --suite core

# 查看报告
open artifacts/eval_reports/20250101/abc12345/report.html
```

### CI/CD 集成

```yaml
# .github/workflows/eval.yml
- name: Run Evaluation
  run: |
    python -m trust_rag.eval.run --suite core --dataset golden_v1
  continue-on-error: false
```

### 程序化使用

```python
from trust_rag.eval.run import run_evaluation
from trust_rag.eval.schema import EvalReport

# 运行评估
report = run_evaluation(suite="core", dataset="golden_v1")

# 检查结果
if report.scorecard.status == "FAIL":
    print("Evaluation failed!")
    for failure in report.scorecard.failures:
        print(f"  - {failure}")
```

## 报告结构

### JSON 报告

```json
{
  "run_meta": {
    "run_id": "eval_20250101_120000",
    "timestamp": "2025-01-01T12:00:00",
    "commit_hash": "abc12345",
    "suite": "core",
    "dataset": "golden_v1"
  },
  "online_query_metrics": {
    "total_queries": 8,
    "stage_latencies": [...],
    "accuracy": {...},
    "retrieval": {...}
  },
  "trust_metrics": {...},
  "cost_metrics": {...},
  "robustness_metrics": {...},
  "scorecard": {
    "overall_score": 85.5,
    "status": "PASS",
    "failures": []
  },
  "top_failures": [...]
}
```

### HTML 报告

包含：
- 评分卡（带状态指示）
- 延迟指标表格和图表
- 准确率指标
- 检索质量指标
- 信任和安全指标
- 成本指标
- 鲁棒性指标
- Top 20 失败案例

## 文件结构

```
trust_rag/eval/
├── __init__.py
├── schema.py              # 数据模型
├── instrumentation.py     # 指标采集
├── judges.py              # 判分器
├── retrieval_eval.py      # 检索评估
├── cost.py                # 成本评估
├── run.py                 # 执行入口
├── report_html.py          # HTML 报告生成
└── datasets/
    ├── __init__.py
    └── golden_v1.jsonl    # 黄金标准数据集

tests/
├── eval/
│   ├── __init__.py
│   └── test_eval_smoke.py # CI 测试
└── perf/
    └── test_extreme_cases.py  # 压测（已修改）
```

## 验收标准

✅ **一键运行**: `python -m trust_rag.eval.run` 可完整运行评估

✅ **报告生成**: 自动生成 JSON 和 HTML 报告

✅ **指标完整**: 包含所有要求的指标

✅ **红线规则**: 自动检查并标记失败

✅ **CI 集成**: 可在 CI 环境中运行

✅ **退出码**: 失败时返回非 0 退出码

## 后续改进建议

1. **更多数据集**: 添加更多黄金标准数据集
2. **可视化增强**: 添加更多图表和可视化
3. **基准对比**: 支持与历史基准对比
4. **自动化报告**: 支持定期自动运行和报告
5. **告警集成**: 红线规则触发时发送告警

---

**完成日期**: 2025-01-XX
**版本**: 1.0

