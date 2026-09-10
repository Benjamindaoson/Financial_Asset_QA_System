#!/usr/bin/env python3
"""
TrustRAG 自动化评价框架 (Evaluation Harness)

实现54条Golden Queries的CI/CD自动化测试：
- 检索召回率监控
- 波动率 >1% 自动阻断发布
- 支持A/B测试和新旧算法对比

核心特性：
- 端到端质量门禁
- 性能回归检测
- 可观测性指标收集
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import statistics
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trust_rag.system import TrustRAG
from trust_rag.config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# P0: Fixed seed for reproducibility
import random
import numpy as np
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


@dataclass
class ReleaseGate:
    """P0: Hard Release Gate with explicit thresholds - no exceptions."""
    # Threshold definitions
    RECALL_AT_5_MIN: float = 0.85
    FAITHFULNESS_MIN: float = 0.95
    REFUSAL_PRECISION_MIN: float = 0.98
    NDCG_AT_5_MIN: float = 0.70
    
    # Evaluation results
    recall_at_5: float = 0.0
    ndcg_at_5: float = 0.0
    faithfulness: float = 0.0
    refusal_precision: float = 0.0
    
    def evaluate(self) -> tuple:
        """Evaluate if release is allowed. Returns (production_ready, reasons)."""
        failures = []
        
        if self.recall_at_5 < self.RECALL_AT_5_MIN:
            failures.append(f"Recall@5={self.recall_at_5:.3f} < {self.RECALL_AT_5_MIN}")
        if self.ndcg_at_5 < self.NDCG_AT_5_MIN:
            failures.append(f"nDCG@5={self.ndcg_at_5:.3f} < {self.NDCG_AT_5_MIN}")
        if self.faithfulness < self.FAITHFULNESS_MIN:
            failures.append(f"Faithfulness={self.faithfulness:.3f} < {self.FAITHFULNESS_MIN}")
        if self.refusal_precision < self.REFUSAL_PRECISION_MIN:
            failures.append(f"RefusalPrecision={self.refusal_precision:.3f} < {self.REFUSAL_PRECISION_MIN}")
        
        production_ready = len(failures) == 0
        return production_ready, failures


@dataclass
class GoldenQuery:
    """黄金标准查询"""
    id: str
    query: str
    expected_chunks: List[str]  # 期望返回的chunk IDs
    expected_answer: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """查询执行结果"""
    query_id: str
    retrieved_chunks: List[str]
    answer: str
    confidence: float
    processing_time: float
    verdict: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvaluationMetrics:
    """评价指标 - P0 Required All Metrics"""
    total_queries: int = 0
    successful_queries: int = 0
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    ndcg_at_5: float = 0.0  # P0: nDCG
    ndcg_at_10: float = 0.0
    faithfulness: float = 0.0  # P0: Answer grounded in evidence
    citation_accuracy: float = 0.0  # P0: Citations correct
    refusal_precision: float = 0.0  # P0: Correct refusals
    refusal_recall: float = 0.0
    avg_confidence: float = 0.0
    avg_processing_time: float = 0.0
    verdict_distribution: Dict[str, int] = field(default_factory=dict)

    # 回归检测
    recall_regression: float = 0.0  # 与基准的偏差
    time_regression: float = 0.0    # 性能回归

    def calculate_recall(self, results: List["QueryResult"], golden_queries: Dict[str, "GoldenQuery"]):
        """计算召回率指标"""
        recall_1_scores = []
        recall_5_scores = []
        recall_10_scores = []

        for result in results:
            golden = golden_queries.get(result.query_id)
            if not golden:
                continue

            expected = set(golden.expected_chunks)
            if not expected:  # Skip refusal queries for recall
                continue
            retrieved = result.retrieved_chunks

            # Recall@K
            recall_1_scores.append(len(expected & set(retrieved[:1])) / len(expected))
            recall_5_scores.append(len(expected & set(retrieved[:5])) / len(expected))
            recall_10_scores.append(len(expected & set(retrieved[:10])) / len(expected))

        self.recall_at_1 = statistics.mean(recall_1_scores) if recall_1_scores else 0.0
        self.recall_at_5 = statistics.mean(recall_5_scores) if recall_5_scores else 0.0
        self.recall_at_10 = statistics.mean(recall_10_scores) if recall_10_scores else 0.0

    def calculate_ndcg(self, results: List["QueryResult"], golden_queries: Dict[str, "GoldenQuery"]):
        """P0: Calculate nDCG@K"""
        ndcg_5_scores = []
        ndcg_10_scores = []
        
        for result in results:
            golden = golden_queries.get(result.query_id)
            if not golden or not golden.expected_chunks:
                continue
            
            expected = set(golden.expected_chunks)
            retrieved = result.retrieved_chunks
            
            # Calculate DCG and IDCG
            def dcg_at_k(retrieved_list, relevant_set, k):
                dcg = 0.0
                for i, chunk_id in enumerate(retrieved_list[:k]):
                    rel = 1.0 if chunk_id in relevant_set else 0.0
                    dcg += rel / np.log2(i + 2)  # i+2 because log2(1)=0
                return dcg
            
            def idcg_at_k(relevant_set, k):
                return dcg_at_k(list(relevant_set)[:k], relevant_set, k)
            
            dcg_5 = dcg_at_k(retrieved, expected, 5)
            idcg_5 = idcg_at_k(expected, 5)
            ndcg_5_scores.append(dcg_5 / idcg_5 if idcg_5 > 0 else 0.0)
            
            dcg_10 = dcg_at_k(retrieved, expected, 10)
            idcg_10 = idcg_at_k(expected, 10)
            ndcg_10_scores.append(dcg_10 / idcg_10 if idcg_10 > 0 else 0.0)
        
        self.ndcg_at_5 = statistics.mean(ndcg_5_scores) if ndcg_5_scores else 0.0
        self.ndcg_at_10 = statistics.mean(ndcg_10_scores) if ndcg_10_scores else 0.0

    def calculate_faithfulness(self, results: List["QueryResult"], golden_queries: Dict[str, "GoldenQuery"]):
        """P0: Calculate Faithfulness - answer grounded in retrieved evidence"""
        faithful_count = 0
        total = 0
        
        for result in results:
            golden = golden_queries.get(result.query_id)
            if not golden or golden.metadata.get("expected_verdict") == "REFUSED":
                continue
            
            total += 1
            # Answer is faithful if verdict is VERIFIED (grounded in evidence)
            if result.verdict == "VERIFIED":
                faithful_count += 1
        
        self.faithfulness = faithful_count / total if total > 0 else 0.0

    def calculate_refusal_metrics(self, results: List["QueryResult"], golden_queries: Dict[str, "GoldenQuery"]):
        """P0: Calculate Refusal Precision and Recall"""
        true_positives = 0  # Correctly refused
        false_positives = 0  # Incorrectly refused
        false_negatives = 0  # Should have refused but didn't
        true_negatives = 0  # Correctly answered
        
        for result in results:
            golden = golden_queries.get(result.query_id)
            if not golden:
                continue
            
            expected_refusal = golden.metadata.get("expected_verdict") == "REFUSED"
            actual_refusal = result.verdict == "REFUSED"
            
            if expected_refusal and actual_refusal:
                true_positives += 1
            elif not expected_refusal and actual_refusal:
                false_positives += 1
            elif expected_refusal and not actual_refusal:
                false_negatives += 1
            else:
                true_negatives += 1
        
        self.refusal_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
        self.refusal_recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0


@dataclass
class EvaluationReport:
    """完整评价报告"""
    run_id: str
    timestamp: datetime
    metrics: EvaluationMetrics
    results: List[QueryResult]
    baseline_comparison: Optional[Dict[str, Any]] = None
    recommendations: List[str] = field(default_factory=list)

    def should_block_deployment(self) -> Tuple[bool, str]:
        """
        判断是否应该阻断部署

        规则：
        1. Recall@5 下降 > 1% → 阻断
        2. 平均置信度下降 > 5% → 阻断
        3. 处理时间增加 > 50% → 阻断
        """
        if not self.baseline_comparison:
            return False, "No baseline available for comparison"

        # 检查召回率回归
        recall_regression = self.baseline_comparison.get('recall_at_5_diff', 0)
        if recall_regression < -0.01:  # 下降超过1%
            return True, ".2%"

        # 检查置信度回归
        confidence_regression = self.baseline_comparison.get('confidence_diff', 0)
        if confidence_regression < -0.05:  # 下降超过5%
            return True, ".1%"

        # 检查性能回归
        time_regression = self.baseline_comparison.get('processing_time_diff', 0)
        if time_regression > 0.5:  # 增加超过50%
            return True, ".1%"

        return False, "All metrics within acceptable range"


class TrustRAGEvaluator:
    """
    TrustRAG 自动化评价器

    实现54条Golden Queries的端到端质量门禁
    """

    def __init__(self, golden_queries_path: str = "trust_rag/eval/datasets/golden_v1.jsonl"):
        self.golden_queries_path = Path(golden_queries_path)
        self.baseline_path = Path("artifacts/eval/baseline.json")

        # 加载黄金查询
        self.golden_queries = self._load_golden_queries()

        # 初始化系统
        self.system = TrustRAG()

        logger.info(f"Loaded {len(self.golden_queries)} golden queries")

    def _load_golden_queries(self) -> Dict[str, GoldenQuery]:
        """加载黄金标准查询"""
        queries = {}

        if not self.golden_queries_path.exists():
            logger.warning(f"Golden queries file not found: {self.golden_queries_path}")
            return queries

        try:
            with open(self.golden_queries_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    query = GoldenQuery(**data)
                    queries[query.id] = query

        except Exception as e:
            logger.error(f"Failed to load golden queries: {e}")

        return queries

    def run_evaluation(self, run_name: str = None) -> EvaluationReport:
        """
        执行完整评价

        Args:
            run_name: 运行名称，用于标识这次评价

        Returns:
            完整评价报告
        """
        run_id = run_name or f"eval_{int(time.time())}"
        logger.info(f"🚀 Starting evaluation run: {run_id}")

        start_time = time.time()
        results = []

        # 执行所有黄金查询
        for query_id, golden_query in self.golden_queries.items():
            try:
                result = self._execute_query(golden_query)
                results.append(result)
                logger.debug(f"✓ Executed query {query_id}")

            except Exception as e:
                logger.error(f"✗ Failed to execute query {query_id}: {e}")
                # 创建失败结果
                results.append(QueryResult(
                    query_id=query_id,
                    retrieved_chunks=[],
                    answer="",
                    confidence=0.0,
                    processing_time=0.0,
                    verdict="ERROR"
                ))

        # 计算指标
        metrics = self._calculate_metrics(results)

        # 加载基准并比较
        baseline_comparison = self._compare_with_baseline(metrics)

        # 生成建议
        recommendations = self._generate_recommendations(metrics, baseline_comparison)

        # 创建报告
        report = EvaluationReport(
            run_id=run_id,
            timestamp=datetime.now(),
            metrics=metrics,
            results=results,
            baseline_comparison=baseline_comparison,
            recommendations=recommendations
        )

        # 保存报告
        self._save_report(report)

        total_time = time.time() - start_time
        logger.info(f"Evaluation completed in {total_time:.1f}s")
        return report

    def _execute_query(self, golden_query: GoldenQuery) -> QueryResult:
        """执行单个查询"""
        start_time = time.time()

        try:
            # 执行查询
            result = self.system.process_query(golden_query.query)

            # 提取检索到的chunks
            # 提取检索到的chunks
            retrieved_chunks = []
            if hasattr(result, 'evidence') and result.evidence:
                # Prioritize evidence_id, fallback to source (doc_id)
                retrieved_chunks = [
                    item.evidence_id or item.source 
                    for item in result.evidence 
                    if item.evidence_id or item.source
                ]

            processing_time = time.time() - start_time

            return QueryResult(
                query_id=golden_query.id,
                retrieved_chunks=retrieved_chunks,
                answer=result.answer.text if result.answer else "",
                confidence=result.answer.confidence if result.answer else 0.0,
                processing_time=processing_time,
                verdict=result.verdict
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Query execution failed: {e}")
            raise

    def _calculate_metrics(self, results: List[QueryResult]) -> EvaluationMetrics:
        """P0: 计算所有评价指标 - 必须全部计算"""
        metrics = EvaluationMetrics()
        metrics.total_queries = len(results)

        # 基础统计
        successful_results = [r for r in results if r.verdict in ["VERIFIED", "CONFLICT"]]
        metrics.successful_queries = len(successful_results)

        if successful_results:
            metrics.avg_confidence = statistics.mean(r.confidence for r in successful_results)
            metrics.avg_processing_time = statistics.mean(r.processing_time for r in successful_results)

        # Verdict分布
        for result in results:
            metrics.verdict_distribution[result.verdict] = \
                metrics.verdict_distribution.get(result.verdict, 0) + 1

        # P0: 召回率计算 (MANDATORY)
        metrics.calculate_recall(results, self.golden_queries)
        
        # P0: nDCG计算 (MANDATORY)
        metrics.calculate_ndcg(results, self.golden_queries)
        
        # P0: Faithfulness计算 (MANDATORY)
        metrics.calculate_faithfulness(results, self.golden_queries)
        
        # P0: Refusal Precision/Recall (MANDATORY)
        metrics.calculate_refusal_metrics(results, self.golden_queries)

        return metrics

    def _compare_with_baseline(self, metrics: EvaluationMetrics) -> Optional[Dict[str, Any]]:
        """与基准比较"""
        if not self.baseline_path.exists():
            logger.info("No baseline found, creating initial baseline")
            self._save_baseline(metrics)
            return None

        try:
            with open(self.baseline_path, 'r', encoding='utf-8') as f:
                baseline = json.load(f)

            comparison = {
                "recall_at_1_diff": metrics.recall_at_1 - baseline.get('recall_at_1', 0),
                "recall_at_5_diff": metrics.recall_at_5 - baseline.get('recall_at_5', 0),
                "recall_at_10_diff": metrics.recall_at_10 - baseline.get('recall_at_10', 0),
                "confidence_diff": metrics.avg_confidence - baseline.get('avg_confidence', 0),
                "processing_time_diff": (metrics.avg_processing_time - baseline.get('avg_processing_time', 0)) / max(baseline.get('avg_processing_time', 1), 0.001)
            }

            return comparison

        except Exception as e:
            logger.error(f"Failed to compare with baseline: {e}")
            return None

    def _save_baseline(self, metrics: EvaluationMetrics):
        """保存基准"""
        try:
            self.baseline_path.parent.mkdir(exist_ok=True)

            baseline = {
                "recall_at_1": metrics.recall_at_1,
                "recall_at_5": metrics.recall_at_5,
                "recall_at_10": metrics.recall_at_10,
                "avg_confidence": metrics.avg_confidence,
                "avg_processing_time": metrics.avg_processing_time,
                "timestamp": datetime.now().isoformat()
            }

            with open(self.baseline_path, 'w', encoding='utf-8') as f:
                json.dump(baseline, f, indent=2, ensure_ascii=False)

            logger.info("Baseline saved")

        except Exception as e:
            logger.error(f"Failed to save baseline: {e}")

    def _generate_recommendations(self, metrics: EvaluationMetrics, baseline_comparison: Optional[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 召回率检查
        if metrics.recall_at_5 < 0.8:
            recommendations.append(f"🟡 WARNING: Recall@5 = {metrics.recall_at_5:.2f}, consider improving retrieval")
        if metrics.recall_at_5 < 0.6:
            recommendations.append("🔴 CRITICAL: Recall@5 extremely low, investigate retrieval system")

        # 性能检查
        if metrics.avg_processing_time > 1.0:
            recommendations.append(f"🟡 WARNING: Average processing time = {metrics.avg_processing_time:.1f}s, consider optimization")
        # 回归检测
        if baseline_comparison:
            recall_diff = baseline_comparison.get('recall_at_5_diff', 0)
            if recall_diff < -0.01:
                recommendations.append(f"🟡 WARNING: Recall@5 decreased by {recall_diff:.2f} compared to baseline")
            if recall_diff < -0.05:
                recommendations.append("🔴 CRITICAL: Major recall regression detected")

        # 成功率检查
        success_rate = metrics.successful_queries / metrics.total_queries
        if success_rate < 0.9:
            recommendations.append(".1%")

        if not recommendations:
            recommendations.append("✅ All metrics look good!")

        return recommendations

    def _save_report(self, report: EvaluationReport):
        """P0: 保存评价报告 - 必须包含完整指标和ReleaseGate"""
        try:
            reports_dir = Path("artifacts/eval/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)

            report_path = reports_dir / f"{report.run_id}.json"
            
            # P0: ReleaseGate evaluation
            gate = ReleaseGate(
                recall_at_5=report.metrics.recall_at_5,
                ndcg_at_5=report.metrics.ndcg_at_5,
                faithfulness=report.metrics.faithfulness,
                refusal_precision=report.metrics.refusal_precision
            )
            production_ready, gate_failures = gate.evaluate()

            # 转换为可序列化格式 - P0: 完整指标
            report_dict = {
                "run_id": report.run_id,
                "timestamp": report.timestamp.isoformat(),
                "random_seed": RANDOM_SEED,
                "metrics": {
                    "total_queries": report.metrics.total_queries,
                    "successful_queries": report.metrics.successful_queries,
                    "recall_at_1": report.metrics.recall_at_1,
                    "recall_at_5": report.metrics.recall_at_5,
                    "recall_at_10": report.metrics.recall_at_10,
                    "ndcg_at_5": report.metrics.ndcg_at_5,
                    "ndcg_at_10": report.metrics.ndcg_at_10,
                    "faithfulness": report.metrics.faithfulness,
                    "citation_accuracy": report.metrics.citation_accuracy,
                    "refusal_precision": report.metrics.refusal_precision,
                    "refusal_recall": report.metrics.refusal_recall,
                    "avg_confidence": report.metrics.avg_confidence,
                    "avg_processing_time": report.metrics.avg_processing_time,
                    "verdict_distribution": report.metrics.verdict_distribution
                },
                "release_gate": {
                    "production_ready": production_ready,
                    "thresholds": {
                        "recall_at_5_min": gate.RECALL_AT_5_MIN,
                        "ndcg_at_5_min": gate.NDCG_AT_5_MIN,
                        "faithfulness_min": gate.FAITHFULNESS_MIN,
                        "refusal_precision_min": gate.REFUSAL_PRECISION_MIN
                    },
                    "failures": gate_failures
                },
                "baseline_comparison": report.baseline_comparison,
                "recommendations": report.recommendations
            }

            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)

            logger.info(f"Evaluation report saved: {report_path}")

            # 打印摘要
            block, reason = report.should_block_deployment()
            if block:
                logger.error(f"🚫 DEPLOYMENT BLOCKED: {reason}")
            else:
                logger.info("✅ Evaluation passed - deployment approved")

        except Exception as e:
            logger.error(f"Failed to save report: {e}")


def main():
    """P0: 主入口函数 - 必须执行完整评价并输出ReleaseGate决策"""
    parser = argparse.ArgumentParser(description="TrustRAG Evaluation Harness")
    parser.add_argument("--run-name", help="Custom run name")
    parser.add_argument("--golden-queries", default="trust_rag/eval/datasets/golden_v1.jsonl",
                       help="Path to golden queries file")
    parser.add_argument("--update-baseline", action="store_true",
                       help="Update baseline with current results")
    parser.add_argument("--ci-mode", action="store_true",
                       help="CI mode - exit with error code if ReleaseGate fails")

    args = parser.parse_args()

    try:
        evaluator = TrustRAGEvaluator(args.golden_queries)
        report = evaluator.run_evaluation(args.run_name)

        if args.update_baseline:
            evaluator._save_baseline(report.metrics)
            logger.info("Baseline updated")

        # P0: ReleaseGate - hard decision
        gate = ReleaseGate(
            recall_at_5=report.metrics.recall_at_5,
            ndcg_at_5=report.metrics.ndcg_at_5,
            faithfulness=report.metrics.faithfulness,
            refusal_precision=report.metrics.refusal_precision
        )
        production_ready, failures = gate.evaluate()
        
        # Print gate result
        print("\n" + "="*60)
        print("RELEASE GATE EVALUATION")
        print("="*60)
        print(f"Recall@5:          {report.metrics.recall_at_5:.3f} (min: {gate.RECALL_AT_5_MIN})")
        print(f"nDCG@5:            {report.metrics.ndcg_at_5:.3f} (min: {gate.NDCG_AT_5_MIN})")
        print(f"Faithfulness:      {report.metrics.faithfulness:.3f} (min: {gate.FAITHFULNESS_MIN})")
        print(f"Refusal Precision: {report.metrics.refusal_precision:.3f} (min: {gate.REFUSAL_PRECISION_MIN})")
        print("-"*60)
        
        if production_ready:
            print("✅ RELEASE GATE: PASS - production_ready = true")
        else:
            print("❌ RELEASE GATE: FAIL - production_ready = false")
            for failure in failures:
                print(f"   - {failure}")
        print("="*60 + "\n")

        # CI模式：基于ReleaseGate设置退出码
        if args.ci_mode:
            if not production_ready:
                logger.error(f"CI FAILURE: ReleaseGate failed - {failures}")
                sys.exit(1)
            else:
                logger.info("CI SUCCESS: ReleaseGate passed")
                sys.exit(0)

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        if args.ci_mode:
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
