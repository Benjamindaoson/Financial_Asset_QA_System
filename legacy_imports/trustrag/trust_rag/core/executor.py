"""
RoutingExecutor: Progressive execution with staged upgrades.
"""
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .profile import QueryProfiler, QueryProfile
from .routing import RoutePlanner, RoutePlan, RouteSpec, RerankPolicy, ConflictPolicy, CrossModalPolicy
from .flags import FeatureFlags, get_flags

logger = logging.getLogger(__name__)

class DegradationLevel(int, Enum):
    L0_FULL = 0
    L1_DEGRADED = 1
    L2_CONFLICT = 2
    L3_NO_EVIDENCE = 3

@dataclass
class ExecutionResult:
    """Result of route execution."""
    evidence_items: List[Any] = field(default_factory=list)
    degradation_level: DegradationLevel = DegradationLevel.L0_FULL
    stages_executed: List[int] = field(default_factory=list)
    upgrades_triggered: List[str] = field(default_factory=list)
    conflicts_detected: List[Any] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    disclosure_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_count": len(self.evidence_items),
            "degradation_level": self.degradation_level.name,
            "stages_executed": self.stages_executed,
            "upgrades_triggered": self.upgrades_triggered,
            "conflicts_count": len(self.conflicts_detected),
            "disclosure_required": self.disclosure_required,
            "metrics": self.metrics
        }

class RoutingExecutor:
    """
    Executes routing plan with progressive upgrades.
    Stage 0: Rules only (0 LLM)
    Stage 1: LLM classifier (if enabled and needed)
    Stage 2: Rerank/Cross-modal (if triggered)
    """
    
    def __init__(
        self,
        profiler: QueryProfiler = None,
        planner: RoutePlanner = None,
        flags: FeatureFlags = None,
        retriever=None,  # Injected retrieval engine
        arbitrator=None,  # Injected EvidenceArbitrator
        conflict_resolver=None  # Injected ConflictResolver
    ):
        self.profiler = profiler or QueryProfiler()
        self.planner = planner or RoutePlanner()
        self.flags = flags or get_flags()
        self.retriever = retriever
        self.arbitrator = arbitrator
        self.conflict_resolver = conflict_resolver
    
    def execute(
        self,
        query: str,
        context: Dict[str, Any] = None,
        ingest_status: str = "OK",
        profile_override: QueryProfile = None
    ) -> Tuple[ExecutionResult, RoutePlan]:
        """
        Execute query with progressive routing.
        """
        context = context or {}
        start_time = time.perf_counter()
        
        result = ExecutionResult()
        result.stages_executed.append(0)
        
        # Stage 0: Profile + Plan (rules only)
        # Use override if provided (e.g. for Financial Mode)
        if profile_override:
            profile = profile_override
            # Re-run specific detections if needed, or assume caller handled it.
            # Ideally, we might want to merge, but replacement is safer for strict modes.
        else:
            profile = self.profiler.profile(query, context)
            
        plan = self.planner.plan(
            profile,
            tenant_id=context.get("tenant_id"),
            domain=context.get("domain"),
            mode=context.get("mode"),
            ingest_status=ingest_status
        )
        
        result.metrics["profile_ms"] = (time.perf_counter() - start_time) * 1000
        
        # Check degradation from ingest
        if ingest_status == "DEGRADED":
            result.degradation_level = DegradationLevel.L1_DEGRADED
            result.disclosure_required = True
        
        # Execute routes
        recall_start = time.perf_counter()
        all_candidates = self._execute_routes(plan.routes, query, plan.budget.max_recall)
        result.metrics["recall_ms"] = (time.perf_counter() - recall_start) * 1000
        result.metrics["candidates_count"] = len(all_candidates)
        
        # Check for upgrade triggers
        upgrades = self._check_upgrade_triggers(all_candidates, profile, plan)
        result.upgrades_triggered = upgrades
        
        # Stage 1: LLM classifier (if needed and enabled)
        if "low_confidence" in upgrades and self.flags.enable_llm_classifier:
            if plan.budget.max_llm_calls > 0:
                result.stages_executed.append(1)
                # Would call LLM here for classification refinement
                plan.budget.max_llm_calls -= 1
        
        # Stage 2: Rerank (if triggered)
        if plan.rerank_policy == RerankPolicy.ON_DEMAND and "top_gap_low" in upgrades:
            if self.flags.enable_rerank:
                result.stages_executed.append(2)
                all_candidates = self._apply_rerank(all_candidates, query, plan.budget.max_rerank)
        
        # Arbitration
        if self.arbitrator:
            arbitrated = self.arbitrator.arbitrate(all_candidates)
        else:
            arbitrated = all_candidates
        
        # Cross-modal verification (if triggered)
        if plan.cross_modal_policy in [CrossModalPolicy.ON_DEMAND, CrossModalPolicy.FORCE]:
            if "numeric_multimodal" in upgrades or plan.cross_modal_policy == CrossModalPolicy.FORCE:
                result.upgrades_triggered.append("cross_modal_verify")
                # Would call CrossModalVerifier here
        
        # Conflict detection
        if plan.conflict_policy in [ConflictPolicy.ON, ConflictPolicy.FORCE]:
            conflicts = self._detect_conflicts(arbitrated)
            result.conflicts_detected = conflicts
            if conflicts:
                result.degradation_level = DegradationLevel.L2_CONFLICT
                result.disclosure_required = True
        
        # No evidence check
        if not arbitrated:
            result.degradation_level = DegradationLevel.L3_NO_EVIDENCE
            result.disclosure_required = True
        
        result.evidence_items = arbitrated
        result.metrics["total_ms"] = (time.perf_counter() - start_time) * 1000
        
        return result, plan
    
    def _execute_routes(self, routes: List[RouteSpec], query: str, max_recall: int) -> List[Any]:
        """Execute retrieval routes."""
        if not self.retriever:
            return []
        
        all_results = []
        remaining = max_recall
        
        # Sort by priority (higher first)
        sorted_routes = sorted(routes, key=lambda r: r.priority, reverse=True)
        
        for route in sorted_routes:
            if remaining <= 0:
                break
            
            # Execute route
            try:
                results = self.retriever.search(
                    query,
                    top_k=min(route.top_k, remaining),
                    strategies=[route.strategy.value] if hasattr(self.retriever, 'search') else None
                )
                all_results.extend(results)
                remaining -= len(results)
            except Exception as e:
                logger.warning(f"Route {route.tier}/{route.strategy} failed: {e}")
                # Fallback: continue with other routes
        
        return all_results
    
    def _check_upgrade_triggers(
        self, 
        candidates: List[Any], 
        profile: QueryProfile,
        plan: RoutePlan
    ) -> List[str]:
        """Check conditions for progressive upgrade."""
        triggers = list(plan.upgrade_triggers)
        
        if not candidates:
            triggers.append("no_candidates")
            return triggers
        
        # Top-1 to Top-10 score gap
        if len(candidates) >= 10:
            scores = sorted([getattr(c, 'score', 0) for c in candidates], reverse=True)
            if scores[0] > 0:
                gap = (scores[0] - scores[9]) / scores[0]
                if gap < self.flags.top_gap_threshold:
                    triggers.append("top_gap_low")
        
        # Coverage check (unique sources)
        if hasattr(candidates[0], 'chunk') if candidates else False:
            sources = set()
            for c in candidates[:20]:
                if hasattr(c.chunk, 'provenance') and c.chunk.provenance:
                    sources.add(c.chunk.provenance.doc_id)
            if len(sources) < 2:
                triggers.append("low_source_coverage")
        
        # Duplicate ratio
        if len(candidates) > 1:
            evidence_ids = [getattr(getattr(c, 'chunk', c), 'evidence_id', '') for c in candidates]
            unique = len(set(evidence_ids))
            dup_ratio = 1 - (unique / len(evidence_ids))
            if dup_ratio > self.flags.duplicate_ratio_threshold:
                triggers.append("high_duplicate_ratio")
        
        return triggers
    
    def _apply_rerank(self, candidates: List[Any], query: str, max_rerank: int) -> List[Any]:
        """Apply reranking to top candidates."""
        # Placeholder: would call reranker here
        return candidates[:max_rerank]
    
    def _detect_conflicts(self, candidates: List[Any]) -> List[Any]:
        """Detect conflicts in evidence."""
        if not self.conflict_resolver:
            return []
        # Placeholder: would call conflict detection here
        return []
