"""
召回率改进监控系统 (Recall Rate Improvement Monitor)

监控和验证TrustRAG检索质量的改进：
- 实时跟踪检索召回率变化
- 对比新旧算法性能差异
- 验证BGE-M3 + 重排序的改进效果
- 提供检索质量趋势分析

核心指标：
- Recall@1, Recall@5, Recall@10
- MRR (Mean Reciprocal Rank)
- NDCG (Normalized Discounted Cumulative Gain)
- 检索质量趋势和回归检测
"""
import logging
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import json

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果记录"""
    query_id: str
    query: str
    retrieved_docs: List[str]  # 检索到的文档ID列表
    ground_truth: List[str]    # 标准答案文档ID列表
    algorithm: str            # 使用的算法 (old/new/bge/baseline)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecallMetrics:
    """召回率指标"""
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mrr: float = 0.0        # Mean Reciprocal Rank
    ndcg_at_5: float = 0.0  # Normalized Discounted Cumulative Gain
    precision_at_5: float = 0.0

    def calculate_from_results(self, results: List[RetrievalResult]):
        """从检索结果计算指标"""
        if not results:
            return

        recall_1_scores = []
        recall_5_scores = []
        recall_10_scores = []
        mrr_scores = []
        ndcg_scores = []
        precision_scores = []

        for result in results:
            retrieved = set(result.retrieved_docs)
            ground_truth = set(result.ground_truth)

            if not ground_truth:
                continue

            # Recall@K
            recall_1_scores.append(len(retrieved & ground_truth) / len(ground_truth))
            recall_5_scores.append(len(retrieved & set(result.retrieved_docs[:5])) / len(ground_truth))
            recall_10_scores.append(len(retrieved & set(result.retrieved_docs[:10])) / len(ground_truth))

            # MRR
            reciprocal_rank = 0
            for rank, doc_id in enumerate(result.retrieved_docs[:10], 1):
                if doc_id in ground_truth:
                    reciprocal_rank = 1.0 / rank
                    break
            mrr_scores.append(reciprocal_rank)

            # NDCG@5 (简化计算)
            ndcg_score = self._calculate_ndcg(result.retrieved_docs[:5], ground_truth)
            ndcg_scores.append(ndcg_score)

            # Precision@5
            retrieved_top5 = set(result.retrieved_docs[:5])
            precision_scores.append(len(retrieved_top5 & ground_truth) / 5)

        # 计算平均值
        self.recall_at_1 = statistics.mean(recall_1_scores) if recall_1_scores else 0.0
        self.recall_at_5 = statistics.mean(recall_5_scores) if recall_5_scores else 0.0
        self.recall_at_10 = statistics.mean(recall_10_scores) if recall_10_scores else 0.0
        self.mrr = statistics.mean(mrr_scores) if mrr_scores else 0.0
        self.ndcg_at_5 = statistics.mean(ndcg_scores) if ndcg_scores else 0.0
        self.precision_at_5 = statistics.mean(precision_scores) if precision_scores else 0.0

    def _calculate_ndcg(self, retrieved: List[str], relevant: set, k: int = 5) -> float:
        """计算NDCG@K (简化版本)"""
        if not retrieved or not relevant:
            return 0.0

        dcg = 0.0
        idcg = 0.0

        # 计算DCG
        for i, doc_id in enumerate(retrieved[:k]):
            if doc_id in relevant:
                dcg += 1.0 / (i + 2)  # log2(i+2)

        # 计算IDCG (理想情况)
        for i in range(min(k, len(relevant))):
            idcg += 1.0 / (i + 2)

        return dcg / idcg if idcg > 0 else 0.0


@dataclass
class AlgorithmComparison:
    """算法对比结果"""
    baseline_metrics: RecallMetrics
    new_metrics: RecallMetrics
    improvement: Dict[str, float]  # 各项指标的改进百分比
    statistical_significance: Dict[str, bool]  # 改进是否显著
    confidence_level: float = 0.95


class RecallImprovementMonitor:
    """
    召回率改进监控器

    核心功能：
    1. 实时监控检索质量指标
    2. 对比新旧算法性能差异
    3. 检测检索质量回归
    4. 验证BGE-M3 + 重排序的改进效果
    """

    def __init__(self, enable_persistence: bool = True):
        self.enable_persistence = enable_persistence

        # 核心数据结构
        self.retrieval_results: List[RetrievalResult] = []
        self.baseline_metrics = RecallMetrics()
        self.current_metrics = RecallMetrics()

        # 算法对比
        self.algorithm_comparisons: List[AlgorithmComparison] = []

        # 线程安全
        self._lock = threading.RLock()

        # 持久化文件
        self.results_log_file = "artifacts/monitoring/recall_results.jsonl"
        self.metrics_file = "artifacts/monitoring/recall_metrics.json"

        # 回归检测阈值
        self.regression_thresholds = {
            "recall_at_5": -0.01,  # 下降超过1%触发警告
            "mrr": -0.02,         # 下降超过2%触发警告
            "critical_drop": -0.05  # 下降超过5%触发警报
        }

        logger.info("Recall Improvement Monitor initialized")

    def record_retrieval_result(
        self,
        query_id: str,
        query: str,
        retrieved_docs: List[str],
        ground_truth: List[str],
        algorithm: str = "current",
        metadata: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        记录检索结果

        Args:
            query_id: 查询ID
            query: 查询文本
            retrieved_docs: 检索到的文档ID列表
            ground_truth: 标准答案文档ID列表
            algorithm: 使用的算法版本
            metadata: 额外元数据

        Returns:
            RetrievalResult记录
        """
        with self._lock:
            result = RetrievalResult(
                query_id=query_id,
                query=query,
                retrieved_docs=retrieved_docs,
                ground_truth=ground_truth,
                algorithm=algorithm,
                metadata=metadata or {}
            )

            self.retrieval_results.append(result)

            # 实时更新当前指标
            current_results = [r for r in self.retrieval_results if r.algorithm == "current"]
            if len(current_results) >= 10:  # 至少10个结果才更新指标
                self.current_metrics.calculate_from_results(current_results)

            # 持久化存储
            if self.enable_persistence:
                self._persist_result(result)

            logger.debug(f"Recorded retrieval result: {query_id} ({algorithm}) - "
                        f"retrieved: {len(retrieved_docs)}, relevant: {len(ground_truth)}")

            return result

    def set_baseline_metrics(self, metrics: RecallMetrics):
        """设置基准指标（用于对比改进效果）"""
        with self._lock:
            self.baseline_metrics = metrics
            logger.info("Baseline metrics updated")

    def calculate_improvement_metrics(self) -> AlgorithmComparison:
        """
        计算改进指标

        Returns:
            算法对比结果
        """
        with self._lock:
            comparison = AlgorithmComparison(
                baseline_metrics=self.baseline_metrics,
                new_metrics=self.current_metrics,
                improvement={},
                statistical_significance={}
            )

            # 计算各项指标的改进
            baseline = comparison.baseline_metrics
            current = comparison.new_metrics

            metrics_to_compare = [
                ('recall_at_1', baseline.recall_at_1, current.recall_at_1),
                ('recall_at_5', baseline.recall_at_5, current.recall_at_5),
                ('recall_at_10', baseline.recall_at_10, current.recall_at_10),
                ('mrr', baseline.mrr, current.mrr),
                ('ndcg_at_5', baseline.ndcg_at_5, current.ndcg_at_5),
                ('precision_at_5', baseline.precision_at_5, current.precision_at_5)
            ]

            for metric_name, baseline_val, current_val in metrics_to_compare:
                if baseline_val > 0:
                    improvement_pct = (current_val - baseline_val) / baseline_val * 100
                else:
                    improvement_pct = 0.0 if current_val == 0 else float('inf')

                comparison.improvement[metric_name] = round(improvement_pct, 2)

                # 简单的显著性检查 (基于样本量和改进幅度)
                current_results = [r for r in self.retrieval_results if r.algorithm == "current"]
                is_significant = (
                    len(current_results) >= 50 and  # 足够样本量
                    abs(improvement_pct) >= 5       # 改进幅度足够大
                )
                comparison.statistical_significance[metric_name] = is_significant

            self.algorithm_comparisons.append(comparison)
            return comparison

    def detect_regression(self) -> Dict[str, Any]:
        """
        检测检索质量回归

        Returns:
            回归检测报告
        """
        with self._lock:
            alerts = []
            warnings = []

            comparison = self.calculate_improvement_metrics()

            for metric_name, improvement in comparison.improvement.items():
                threshold = self.regression_thresholds.get(metric_name, -0.01)

                if improvement <= self.regression_thresholds.get("critical_drop", -0.05):
                    alerts.append({
                        "level": "CRITICAL",
                        "metric": metric_name,
                        "improvement": improvement,
                        "threshold": self.regression_thresholds.get("critical_drop", -0.05),
                        "message": ".2f"                    })
                elif improvement <= threshold:
                    warnings.append({
                        "level": "WARNING",
                        "metric": metric_name,
                        "improvement": improvement,
                        "threshold": threshold,
                        "message": ".2f"                    })

            return {
                "alerts": alerts,
                "warnings": warnings,
                "status": "CRITICAL" if alerts else ("WARNING" if warnings else "OK"),
                "current_improvement": comparison.improvement,
                "timestamp": datetime.now().isoformat()
            }

    def get_quality_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        获取检索质量趋势

        Args:
            days: 分析天数

        Returns:
            质量趋势报告
        """
        with self._lock:
            cutoff_date = datetime.now() - timedelta(days=days)

            # 按日期分组结果
            daily_results = defaultdict(list)
            for result in self.retrieval_results:
                if result.timestamp >= cutoff_date:
                    date_key = result.timestamp.date()
                    daily_results[date_key].append(result)

            # 计算每日指标
            daily_metrics = {}
            for date, results in daily_results.items():
                if len(results) >= 5:  # 最少5个结果才有意义
                    metrics = RecallMetrics()
                    metrics.calculate_from_results(results)
                    daily_metrics[date] = {
                        "recall_at_5": metrics.recall_at_5,
                        "mrr": metrics.mrr,
                        "sample_count": len(results)
                    }

            # 计算趋势
            trends = {}
            sorted_dates = sorted(daily_metrics.keys())

            for metric in ["recall_at_5", "mrr"]:
                values = [daily_metrics[date][metric] for date in sorted_dates]

                if len(values) >= 2:
                    # 计算趋势斜率
                    x = list(range(len(values)))
                    slope, intercept = statistics.linear_regression(x, values)

                    # 判断趋势方向
                    if slope > 0.001:
                        trend = "improving"
                    elif slope < -0.001:
                        trend = "declining"
                    else:
                        trend = "stable"

                    trends[metric] = {
                        "values": values,
                        "dates": [str(d) for d in sorted_dates],
                        "slope": round(slope, 6),
                        "trend": trend,
                        "latest_value": values[-1],
                        "avg_value": statistics.mean(values)
                    }

            return {
                "analysis_period_days": days,
                "trends": trends,
                "daily_metrics": {str(k): v for k, v in daily_metrics.items()},
                "recommendations": self._generate_trend_recommendations(trends)
            }

    def validate_bge_improvement(self) -> Dict[str, Any]:
        """
        验证BGE-M3 + 重排序的改进效果

        Returns:
            BGE改进验证报告
        """
        with self._lock:
            # 获取不同算法的结果
            algorithm_results = defaultdict(list)
            for result in self.retrieval_results:
                algorithm_results[result.algorithm].append(result)

            if "baseline" not in algorithm_results or "bge" not in algorithm_results:
                return {"error": "Insufficient data for BGE validation"}

            # 计算各算法的指标
            baseline_metrics = RecallMetrics()
            baseline_metrics.calculate_from_results(algorithm_results["baseline"])

            bge_metrics = RecallMetrics()
            bge_metrics.calculate_from_results(algorithm_results["bge"])

            # 计算改进
            improvements = {}
            for attr in ["recall_at_1", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5"]:
                baseline_val = getattr(baseline_metrics, attr)
                bge_val = getattr(bge_metrics, attr)

                if baseline_val > 0:
                    improvement = (bge_val - baseline_val) / baseline_val * 100
                else:
                    improvement = 0.0

                improvements[attr] = round(improvement, 2)

            # 验证是否达到预期改进
            expected_improvements = {
                "recall_at_5": 20,  # 期望至少20%的改进
                "mrr": 15,
                "ndcg_at_5": 25
            }

            validation_results = {}
            for metric, expected in expected_improvements.items():
                actual = improvements.get(metric, 0)
                validation_results[metric] = {
                    "expected_improvement": expected,
                    "actual_improvement": actual,
                    "status": "✅ PASSED" if actual >= expected else "❌ FAILED"
                }

            return {
                "baseline_metrics": {
                    "recall_at_5": baseline_metrics.recall_at_5,
                    "mrr": baseline_metrics.mrr,
                    "ndcg_at_5": baseline_metrics.ndcg_at_5,
                    "sample_count": len(algorithm_results["baseline"])
                },
                "bge_metrics": {
                    "recall_at_5": bge_metrics.recall_at_5,
                    "mrr": bge_metrics.mrr,
                    "ndcg_at_5": bge_metrics.ndcg_at_5,
                    "sample_count": len(algorithm_results["bge"])
                },
                "improvements": improvements,
                "validation_results": validation_results,
                "overall_status": "PASSED" if all(r["status"].startswith("✅") for r in validation_results.values()) else "FAILED"
            }

    def _generate_trend_recommendations(self, trends: Dict[str, Any]) -> List[str]:
        """生成趋势分析建议"""
        recommendations = []

        recall_trend = trends.get("recall_at_5", {})
        mrr_trend = trends.get("mrr", {})

        # 检查召回率趋势
        if recall_trend.get("trend") == "declining":
            recommendations.append("⚠️ 召回率呈下降趋势，建议检查检索算法或数据质量")
        elif recall_trend.get("trend") == "improving":
            recommendations.append("✅ 召回率持续提升，改进策略有效")

        # 检查MRR趋势
        if mrr_trend.get("trend") == "declining":
            recommendations.append("⚠️ MRR呈下降趋势，可能影响用户体验")

        # 检查稳定性
        if recall_trend.get("slope", 0) < -0.0001:  # 显著下降
            recommendations.append("🔴 检索质量显著下降，需要立即调查")

        if not recommendations:
            recommendations.append("✅ 检索质量保持稳定")

        return recommendations

    def _persist_result(self, result: RetrievalResult):
        """持久化检索结果"""
        try:
            import os
            os.makedirs(os.path.dirname(self.results_log_file), exist_ok=True)

            with open(self.results_log_file, 'a', encoding='utf-8') as f:
                record = {
                    "query_id": result.query_id,
                    "query": result.query,
                    "retrieved_docs": result.retrieved_docs,
                    "ground_truth": result.ground_truth,
                    "algorithm": result.algorithm,
                    "timestamp": result.timestamp.isoformat(),
                    "metadata": result.metadata
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        except Exception as e:
            logger.warning(f"Failed to persist retrieval result: {e}")

    def export_monitoring_report(self) -> Dict[str, Any]:
        """导出完整的监控报告"""
        with self._lock:
            comparison = self.calculate_improvement_metrics()
            regression_report = self.detect_regression()
            trends_report = self.get_quality_trends()
            bge_validation = self.validate_bge_improvement()

            return {
                "timestamp": datetime.now().isoformat(),
                "current_metrics": {
                    "recall_at_1": self.current_metrics.recall_at_1,
                    "recall_at_5": self.current_metrics.recall_at_5,
                    "recall_at_10": self.current_metrics.recall_at_10,
                    "mrr": self.current_metrics.mrr,
                    "ndcg_at_5": self.current_metrics.ndcg_at_5,
                    "precision_at_5": self.current_metrics.precision_at_5,
                    "sample_count": len([r for r in self.retrieval_results if r.algorithm == "current"])
                },
                "baseline_metrics": {
                    "recall_at_1": self.baseline_metrics.recall_at_1,
                    "recall_at_5": self.baseline_metrics.recall_at_5,
                    "recall_at_10": self.baseline_metrics.recall_at_10,
                    "mrr": self.baseline_metrics.mrr,
                    "ndcg_at_5": self.baseline_metrics.ndcg_at_5,
                    "precision_at_5": self.baseline_metrics.precision_at_5
                },
                "algorithm_comparison": {
                    "improvements": comparison.improvement,
                    "statistical_significance": comparison.statistical_significance
                },
                "regression_detection": regression_report,
                "quality_trends": trends_report,
                "bge_validation": bge_validation,
                "overall_status": (
                    "CRITICAL" if regression_report["status"] == "CRITICAL"
                    else "WARNING" if regression_report["status"] == "WARNING"
                    else "HEALTHY"
                )
            }


# 全局召回率监控器实例
_recall_monitor = None

def get_recall_monitor() -> RecallImprovementMonitor:
    """获取全局召回率监控器实例"""
    global _recall_monitor
    if _recall_monitor is None:
        _recall_monitor = RecallImprovementMonitor()
    return _recall_monitor

# 便捷函数
def record_retrieval_result(*args, **kwargs):
    """便捷函数：记录检索结果"""
    return get_recall_monitor().record_retrieval_result(*args, **kwargs)

def get_recall_improvement_report():
    """获取召回率改进报告"""
    monitor = get_recall_monitor()
    comparison = monitor.calculate_improvement_metrics()
    return {
        "improvements": comparison.improvement,
        "current_metrics": {
            "recall_at_5": monitor.current_metrics.recall_at_5,
            "mrr": monitor.current_metrics.mrr
        },
        "baseline_metrics": {
            "recall_at_5": monitor.baseline_metrics.recall_at_5,
            "mrr": monitor.baseline_metrics.mrr
        }
    }
