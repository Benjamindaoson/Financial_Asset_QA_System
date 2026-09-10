"""
Token Cost Tracker System.

Monitors and optimizes TrustRAG token usage costs:
- Real-time tracking of token consumption per component.
- Analysis of cost optimization effectiveness (Target: 60% reduction).
- Provides cost forecasting and budget control.
- Supports tiered parsing cost comparison analysis.

Key Metrics:
- Total token consumption.
- Consumption distribution by component.
- Cost optimization efficiency.
- Future cost forecasting.
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
class TokenUsage:
    """Token usage record"""
    component: str
    operation: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostMetrics:
    """Cost metrics"""
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    cost_per_query: float = 0.0
    queries_count: int = 0
    avg_tokens_per_query: float = 0.0
    cost_trend: List[float] = field(default_factory=list)  # Hourly cost for last 24h


@dataclass
class ParsingTierStats:
    """Tiered parsing statistics"""
    tier_name: str
    documents_processed: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_tokens_per_doc: float = 0.0
    avg_cost_per_doc: float = 0.0
    token_savings_percent: float = 0.0  # Savings compared to traditional parsing


class TokenCostTracker:
    """
    Token cost tracking and optimization analyzer.

    Core Functions:
    1. Real-time token consumption monitoring.
    2. Cost optimization effect analysis.
    3. Tiered parsing ROI calculation.
    4. Budget control and alerts.
    """

    def __init__(self, enable_persistence: bool = True):
        self.enable_persistence = enable_persistence

        # Core data structures
        self.usage_records: List[TokenUsage] = []
        self.cost_metrics = CostMetrics()

        # Tiered parsing statistics
        self.parsing_stats: Dict[str, ParsingTierStats] = {
            "lightweight": ParsingTierStats(tier_name="lightweight"),
            "vlm_enhanced": ParsingTierStats(tier_name="vlm_enhanced"),
            "traditional": ParsingTierStats(tier_name="traditional")  # Benchmark
        }

        # Component-level statistics
        self.component_stats: Dict[str, CostMetrics] = defaultdict(CostMetrics)

        # Thread safety
        self._lock = threading.RLock()

        # Persistence files
        self.usage_log_file = "artifacts/monitoring/token_usage.jsonl"
        self.metrics_file = "artifacts/monitoring/cost_metrics.json"

        # Token Pricing (USD per 1K tokens)
        self.pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "claude-3": {"input": 0.015, "output": 0.075},
            "embedding": {"input": 0.0001},  # Per 1K tokens
            "vlm_parsing": {"per_call": 0.1},  # Fixed cost per VLM call
        }

        logger.info("Token Cost Tracker initialized")

    def record_usage(
        self,
        component: str,
        operation: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None
    ) -> TokenUsage:
        """
        Record token usage.

        Args:
            component: Component name (parsing, retrieval, generation, etc.)
            operation: Operation name
            input_tokens: Input token count
            output_tokens: Output token count
            model: Model used
            metadata: Extra metadata

        Returns:
            TokenUsage record
        """
        with self._lock:
            # 计算总Token和成本
            total_tokens = input_tokens + output_tokens
            cost_usd = self._calculate_cost(model, input_tokens, output_tokens, component)

            # 创建使用记录
            usage = TokenUsage(
                component=component,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                metadata=metadata or {}
            )

            # 添加到记录列表
            self.usage_records.append(usage)

            # 更新组件统计
            comp_stats = self.component_stats[component]
            comp_stats.total_cost_usd += cost_usd
            comp_stats.total_tokens += total_tokens
            comp_stats.queries_count += 1

            # 更新全局统计
            self.cost_metrics.total_cost_usd += cost_usd
            self.cost_metrics.total_tokens += total_tokens
            self.cost_metrics.queries_count += 1

            # Persist usage
            if self.enable_persistence:
                self._persist_usage(usage)

            logger.debug(f"Recorded token usage: {component}.{operation} - "
                        f"{total_tokens} tokens, ${cost_usd:.4f}")

            return usage

    def record_parsing_usage(
        self,
        tier: str,
        tokens_used: int = 0,
        model: str = "vlm_parsing",
        document_size: int = 0
    ):
        """
        Record parsing related token usage.

        Args:
            tier: Parsing tier (lightweight/vlm_enhanced/traditional)
            tokens_used: Tokens consumed
            model: Model used
            document_size: Document size (characters)
        """
        if tier not in self.parsing_stats:
            self.parsing_stats[tier] = ParsingTierStats(tier_name=tier)

        stats = self.parsing_stats[tier]
        stats.documents_processed += 1
        stats.total_tokens += tokens_used

        # 计算成本
        cost = self._calculate_cost(model, tokens_used, 0, "parsing")
        stats.total_cost += cost

        # Update average values
        if stats.documents_processed > 0:
            stats.avg_tokens_per_doc = stats.total_tokens / stats.documents_processed
            stats.avg_cost_per_doc = stats.total_cost / stats.documents_processed

        # Calculate token savings percentage (vs traditional)
        if tier == "lightweight":
            traditional_stats = self.parsing_stats.get("traditional")
            if traditional_stats and traditional_stats.documents_processed > 0:
                traditional_avg = traditional_stats.avg_tokens_per_doc
                if traditional_avg > 0:
                    stats.token_savings_percent = (1 - stats.avg_tokens_per_doc / traditional_avg) * 100

    def get_cost_metrics(self, time_window_hours: int = 24) -> CostMetrics:
        """
        Get cost metrics.

        Args:
            time_window_hours: Time window (hours)

        Returns:
            Cost metrics
        """
        with self._lock:
            # 过滤时间窗口内的记录
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
            recent_records = [
                r for r in self.usage_records
                if r.timestamp > cutoff_time
            ]

            if not recent_records:
                return CostMetrics()

            # 计算指标
            metrics = CostMetrics()
            metrics.queries_count = len(recent_records)
            metrics.total_cost_usd = sum(r.cost_usd for r in recent_records)
            metrics.total_tokens = sum(r.total_tokens for r in recent_records)

            if metrics.queries_count > 0:
                metrics.cost_per_query = metrics.total_cost_usd / metrics.queries_count
                metrics.avg_tokens_per_query = metrics.total_tokens / metrics.queries_count

            # Cost trend (hourly)
            hourly_costs = defaultdict(float)
            for record in recent_records:
                hour_key = record.timestamp.replace(minute=0, second=0, microsecond=0)
                hourly_costs[hour_key] += record.cost_usd

            metrics.cost_trend = [hourly_costs[h] for h in sorted(hourly_costs.keys())]

            return metrics

    def get_parsing_efficiency_report(self) -> Dict[str, Any]:
        """
        Get tiered parsing efficiency report.

        Returns:
            Parsing efficiency analysis report
        """
        with self._lock:
            report = {
                "timestamp": datetime.now().isoformat(),
                "parsing_tiers": {},
                "overall_efficiency": {},
                "recommendations": []
            }

            # Tiered statistics
            for tier_name, stats in self.parsing_stats.items():
                if stats.documents_processed > 0:
                    report["parsing_tiers"][tier_name] = {
                        "documents_processed": stats.documents_processed,
                        "total_tokens": stats.total_tokens,
                        "total_cost": round(stats.total_cost, 4),
                        "avg_tokens_per_doc": round(stats.avg_tokens_per_doc, 2),
                        "avg_cost_per_doc": round(stats.avg_cost_per_doc, 4),
                        "token_savings_percent": round(stats.token_savings_percent, 2)
                    }

            # Overall efficiency analysis
            lightweight = report["parsing_tiers"].get("lightweight", {})
            vlm_enhanced = report["parsing_tiers"].get("vlm_enhanced", {})

            if lightweight and vlm_enhanced:
                total_docs = lightweight["documents_processed"] + vlm_enhanced["documents_processed"]
                if total_docs > 0:
                    # Weighted average cost
                    weighted_cost = (
                        lightweight["avg_cost_per_doc"] * lightweight["documents_processed"] +
                        vlm_enhanced["avg_cost_per_doc"] * vlm_enhanced["documents_processed"]
                    ) / total_docs

                    report["overall_efficiency"] = {
                        "total_documents": total_docs,
                        "weighted_avg_cost_per_doc": round(weighted_cost, 4),
                        "lightweight_ratio": lightweight["documents_processed"] / total_docs,
                        "vlm_ratio": vlm_enhanced["documents_processed"] / total_docs,
                        "target_achievement": "✅ Reached 60% savings target" if lightweight.get("token_savings_percent", 0) >= 60 else "⚠️ Target not reached"
                    }

            # Generate recommendations
            recommendations = []
            if lightweight.get("token_savings_percent", 0) < 60:
                recommendations.append("⚠️ Token savings rate below 60% target, consider optimizing lightweight parsing strategy")

            vlm_ratio = report["overall_efficiency"].get("vlm_ratio", 0)
            if vlm_ratio > 0.3:
                recommendations.append("ℹ️ VLM usage higher than expected (>30%), monitor costs carefully")
            elif vlm_ratio < 0.1:
                recommendations.append("ℹ️ VLM usage low, consider relaxing complexity thresholds")

            report["recommendations"] = recommendations

            return report

    def get_cost_predictions(self, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Predict future costs.

        Args:
            days_ahead: Prediction days

        Returns:
            Cost prediction report
        """
        with self._lock:
            # Simple prediction based on historical data
            recent_metrics = self.get_cost_metrics(time_window_hours=24)

            if not recent_metrics.cost_trend:
                return {"error": "Insufficient historical data for prediction"}

            # Calculate daily average cost
            daily_cost = statistics.mean(recent_metrics.cost_trend) * 24

            # Simple linear trend prediction
            trend_slope = 0
            if len(recent_metrics.cost_trend) > 1:
                # Calculate trend slope
                x = list(range(len(recent_metrics.cost_trend)))
                y = recent_metrics.cost_trend
                trend_slope = statistics.linear_regression(x, y)[0]

            predictions = []
            current_daily = daily_cost

            for day in range(1, days_ahead + 1):
                # Simple prediction: Current level + trend
                predicted_daily = max(0, current_daily + trend_slope * day)
                predictions.append({
                    "day": day,
                    "predicted_daily_cost": round(predicted_daily, 2),
                    "predicted_cumulative": round(sum(predictions[:day]), 2)
                })

            return {
                "current_daily_cost": round(daily_cost, 2),
                "trend_slope": round(trend_slope, 4),
                "predictions": predictions,
                "total_predicted_cost": round(sum(p["predicted_daily_cost"] for p in predictions), 2)
            }

    def check_budget_limits(self, daily_limit: float = 10.0, monthly_limit: float = 300.0) -> Dict[str, Any]:
        """
        Check budget limits.

        Args:
            daily_limit: Daily budget limit
            monthly_limit: Monthly budget limit

        Returns:
            Budget check report
        """
        with self._lock:
            daily_metrics = self.get_cost_metrics(time_window_hours=24)
            monthly_metrics = self.get_cost_metrics(time_window_hours=24*30)

            alerts = []

            if daily_metrics.total_cost_usd > daily_limit:
                alerts.append({
                    "level": "CRITICAL",
                    "type": "daily_budget_exceeded",
                    "message": f"Daily budget exceeded: ${daily_metrics.total_cost_usd:.2f}",
                    "current": round(daily_metrics.total_cost_usd, 2),
                    "limit": daily_limit
                })

            if monthly_metrics.total_cost_usd > monthly_limit:
                alerts.append({
                    "level": "WARNING",
                    "type": "monthly_budget_exceeded",
                    "message": f"Monthly budget exceeded: ${monthly_metrics.total_cost_usd:.2f}",
                    "current": round(monthly_metrics.total_cost_usd, 2),
                    "limit": monthly_limit
                })

            return {
                "daily_cost": round(daily_metrics.total_cost_usd, 2),
                "monthly_cost": round(monthly_metrics.total_cost_usd, 2),
                "daily_limit": daily_limit,
                "monthly_limit": monthly_limit,
                "alerts": alerts,
                "status": "OK" if not alerts else "ALERT"
            }

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int, component: str) -> float:
        """Calculate token cost"""
        try:
            if component == "parsing" and model == "vlm_parsing":
                # VLM parsing fixed cost
                return self.pricing["vlm_parsing"]["per_call"]

            elif component == "embedding":
                # Embedding cost (per 1K tokens)
                return (input_tokens / 1000) * self.pricing["embedding"]["input"]

            elif model in self.pricing:
                # LLM cost
                pricing = self.pricing[model]
                input_cost = (input_tokens / 1000) * pricing["input"]
                output_cost = (output_tokens / 1000) * pricing["output"]
                return input_cost + output_cost

            else:
                # Default cost estimation
                return (input_tokens + output_tokens) * 0.0001

        except (KeyError, TypeError):
            logger.warning(f"Unknown pricing for model {model}, using default")
            return (input_tokens + output_tokens) * 0.0001

    def _persist_usage(self, usage: TokenUsage):
        """Persist token usage records"""
        try:
            import os
            os.makedirs(os.path.dirname(self.usage_log_file), exist_ok=True)

            with open(self.usage_log_file, 'a', encoding='utf-8') as f:
                record = {
                    "timestamp": usage.timestamp.isoformat(),
                    "component": usage.component,
                    "operation": usage.operation,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": usage.cost_usd,
                    "metadata": usage.metadata
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        except Exception as e:
            logger.warning(f"Failed to persist usage record: {e}")

    def export_metrics_report(self) -> Dict[str, Any]:
        """Export comprehensive metrics report"""
        with self._lock:
            return {
                "timestamp": datetime.now().isoformat(),
                "cost_metrics": {
                    "total_cost_usd": round(self.cost_metrics.total_cost_usd, 4),
                    "total_tokens": self.cost_metrics.total_tokens,
                    "queries_count": self.cost_metrics.queries_count,
                    "cost_per_query": round(self.cost_metrics.cost_per_query, 4),
                    "avg_tokens_per_query": round(self.cost_metrics.avg_tokens_per_query, 2)
                },
                "parsing_efficiency": self.get_parsing_efficiency_report(),
                "cost_predictions": self.get_cost_predictions(days_ahead=7),
                "budget_status": self.check_budget_limits(),
                "component_breakdown": {
                    comp: {
                        "total_cost": round(stats.total_cost_usd, 4),
                        "total_tokens": stats.total_tokens,
                        "queries_count": stats.queries_count
                    }
                    for comp, stats in self.component_stats.items()
                }
            }


# 全局Token成本跟踪器实例
_token_tracker = None

def get_token_tracker() -> TokenCostTracker:
    """Get global TokenCostTracker instance"""
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenCostTracker()
    return _token_tracker

# Convenience decorator
def track_token_usage(component: str, operation: str, model: str = "unknown"):
    """
    Token usage tracking decorator.

    Args:
        component: Component name
        operation: Operation name
        model: Model identifier
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracker = get_token_tracker()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                # Estimate token usage (simplified implementation)
                # In actual usage, this should be extracted from API response metadata
                estimated_tokens = getattr(result, 'usage', {}).get('total_tokens', 100)

                tracker.record_usage(
                    component=component,
                    operation=operation,
                    total_tokens=estimated_tokens,
                    model=model,
                    metadata={
                        "function": func.__name__,
                        "execution_time": time.time() - start_time
                    }
                )

                return result

            except Exception as e:
                # 记录失败的操作
                tracker.record_usage(
                    component=component,
                    operation=f"{operation}_failed",
                    total_tokens=0,
                    cost_usd=0.0,
                    model=model,
                    metadata={"error": str(e)}
                )
                raise

        return wrapper
    return decorator
