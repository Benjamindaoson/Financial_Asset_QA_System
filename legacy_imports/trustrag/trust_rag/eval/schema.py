"""
Evaluation Schema Definitions.

Defines Pydantic models for evaluation metrics and reports.
"""
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class RunMeta(BaseModel):
    """Metadata for evaluation run."""
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    suite: Literal["core", "full"] = "core"
    dataset: str = "golden_v1"
    environment: str = "local"
    notes: Optional[str] = None


class StageLatency(BaseModel):
    """Latency metrics for a processing stage."""
    stage_name: str
    count: int = 0
    total_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    
    def calculate_percentiles(self, latencies: List[float]):
        """Calculate percentiles from latency list."""
        if not latencies:
            return
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        self.count = n
        self.total_ms = sum(sorted_latencies)
        self.min_ms = sorted_latencies[0]
        self.max_ms = sorted_latencies[-1]
        self.avg_ms = self.total_ms / n
        
        self.p50_ms = sorted_latencies[int(n * 0.50)]
        self.p95_ms = sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[0]
        self.p99_ms = sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[0]


class MetricSeries(BaseModel):
    """Time series of a metric."""
    metric_name: str
    timestamps: List[str] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)
    unit: str = ""


class CostMetrics(BaseModel):
    """Cost and resource usage metrics."""
    # Token usage (if LLM enabled)
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    token_cost_usd: float = 0.0
    
    # Resource usage
    total_cpu_ms: float = 0.0
    total_mem_mb: float = 0.0
    peak_mem_mb: float = 0.0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    index_size_mb: float = 0.0
    
    # Derived metrics
    cost_per_query_usd: float = 0.0
    cost_per_page_usd: float = 0.0
    cpu_per_query_ms: float = 0.0
    mem_per_query_mb: float = 0.0


class RetrievalMetrics(BaseModel):
    """Retrieval quality metrics."""
    # Recall metrics
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    
    # MRR (Mean Reciprocal Rank)
    mrr_at_5: float = 0.0
    mrr_at_10: float = 0.0
    
    # NDCG (Normalized Discounted Cumulative Gain)
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0
    
    # Rerank comparison
    rerank_gain_recall: float = 0.0  # Improvement after reranking
    rerank_gain_mrr: float = 0.0
    rerank_gain_ndcg: float = 0.0
    
    # Average metrics
    avg_candidates_per_query: float = 0.0
    avg_relevant_candidates: float = 0.0


class IngestMetrics(BaseModel):
    """Document ingestion quality metrics."""
    total_documents: int = 0
    successful_ingests: int = 0
    degraded_ingests: int = 0
    failed_ingests: int = 0
    
    total_chunks: int = 0
    avg_chunks_per_doc: float = 0.0
    
    # Quality metrics
    avg_ocr_confidence: float = 0.0
    avg_text_quality_score: float = 0.0
    
    # Performance
    avg_ingest_time_ms: float = 0.0
    total_ingest_time_ms: float = 0.0
    
    # Errors
    error_types: Dict[str, int] = Field(default_factory=dict)
    error_messages: List[str] = Field(default_factory=list)


class TrustMetrics(BaseModel):
    """Trust and safety metrics."""
    # Refusal metrics
    total_refusals: int = 0
    correct_refusals: int = 0  # Refused when should refuse
    incorrect_refusals: int = 0  # Refused when should answer
    missed_refusals: int = 0  # Answered when should refuse
    
    refusal_precision: float = 0.0
    refusal_recall: float = 0.0
    refusal_f1: float = 0.0
    
    # Evidence support
    total_queries: int = 0
    queries_with_evidence: int = 0
    evidence_support_rate: float = 0.0
    avg_evidence_per_query: float = 0.0
    
    # Post-verification
    verification_checks: int = 0
    verification_passed: int = 0
    verification_failed: int = 0
    verification_pass_rate: float = 0.0
    
    # Risk flags
    high_risk_queries: int = 0
    risk_flags_triggered: Dict[str, int] = Field(default_factory=dict)
    
    # Hallucination detection
    unsupported_claims: int = 0
    high_risk_misanswers: int = 0


class RobustnessMetrics(BaseModel):
    """Robustness and extreme case metrics."""
    # Extreme case tests
    ultra_long_doc_test: Dict[str, Any] = Field(default_factory=dict)
    batch_large_files_test: Dict[str, Any] = Field(default_factory=dict)
    special_formats_test: Dict[str, Any] = Field(default_factory=dict)
    concurrent_queries_test: Dict[str, Any] = Field(default_factory=dict)
    
    # Overall robustness
    total_extreme_tests: int = 0
    passed_extreme_tests: int = 0
    robustness_score: float = 0.0
    
    # Failure analysis
    failure_reasons: Dict[str, int] = Field(default_factory=dict)
    failure_cases: List[Dict[str, Any]] = Field(default_factory=list)


class AccuracyMetrics(BaseModel):
    """Accuracy evaluation metrics."""
    # Exact match
    exact_match_count: int = 0
    exact_match_rate: float = 0.0
    
    # Numeric accuracy
    numeric_queries: int = 0
    numeric_correct: int = 0
    numeric_error_rate: float = 0.0
    avg_numeric_error: float = 0.0
    max_numeric_error: float = 0.0
    
    # Evidence support
    evidence_supported_count: int = 0
    evidence_support_rate: float = 0.0
    
    # Overall
    total_queries: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0


class Scorecard(BaseModel):
    """Overall scorecard with pass/fail indicators."""
    overall_score: float = 0.0  # 0-100
    status: Literal["PASS", "FAIL", "WARNING"] = "PASS"
    
    # Red line rules
    high_risk_misanswers: int = 0
    unsupported_claims: int = 0
    p95_latency_ms: float = 0.0
    p95_latency_threshold_ms: float = 5000.0
    
    # Component scores
    latency_score: float = 0.0
    accuracy_score: float = 0.0
    retrieval_score: float = 0.0
    trust_score: float = 0.0
    robustness_score: float = 0.0
    cost_score: float = 0.0
    
    # Failures
    failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    def check_red_lines(self):
        """Check red line rules and update status."""
        self.failures = []
        self.warnings = []
        
        if self.high_risk_misanswers > 0:
            self.failures.append(f"High-risk misanswers detected: {self.high_risk_misanswers}")
        
        if self.unsupported_claims > 0:
            self.failures.append(f"Unsupported claims detected: {self.unsupported_claims}")
        
        if self.p95_latency_ms > self.p95_latency_threshold_ms:
            self.failures.append(
                f"P95 latency {self.p95_latency_ms:.0f}ms exceeds threshold "
                f"{self.p95_latency_threshold_ms:.0f}ms"
            )
        
        if self.failures:
            self.status = "FAIL"
        elif self.warnings:
            self.status = "WARNING"
        else:
            self.status = "PASS"


class OnlineQueryMetrics(BaseModel):
    """Metrics for online query processing."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    
    # Latency by stage
    stage_latencies: List[StageLatency] = Field(default_factory=list)
    
    # Throughput
    queries_per_second: float = 0.0
    concurrent_queries: int = 0
    max_concurrent: int = 0
    
    # Accuracy
    accuracy: AccuracyMetrics = Field(default_factory=AccuracyMetrics)
    
    # Retrieval
    retrieval: RetrievalMetrics = Field(default_factory=RetrievalMetrics)
    
    # Trust
    trust: TrustMetrics = Field(default_factory=TrustMetrics)


class OfflineIngestMetrics(BaseModel):
    """Metrics for offline document ingestion."""
    ingest: IngestMetrics = Field(default_factory=IngestMetrics)
    
    # Cost
    ingest_cost: CostMetrics = Field(default_factory=CostMetrics)


class EvalReport(BaseModel):
    """Complete evaluation report."""
    run_meta: RunMeta
    
    # Metrics sections
    offline_ingest_metrics: OfflineIngestMetrics = Field(default_factory=OfflineIngestMetrics)
    online_query_metrics: OnlineQueryMetrics = Field(default_factory=OnlineQueryMetrics)
    trust_metrics: TrustMetrics = Field(default_factory=TrustMetrics)
    cost_metrics: CostMetrics = Field(default_factory=CostMetrics)
    robustness_metrics: RobustnessMetrics = Field(default_factory=RobustnessMetrics)
    
    # Scorecard
    scorecard: Scorecard = Field(default_factory=Scorecard)
    
    # Artifacts
    artifacts_links: Dict[str, str] = Field(default_factory=dict)
    
    # Top failures
    top_failures: List[Dict[str, Any]] = Field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()

