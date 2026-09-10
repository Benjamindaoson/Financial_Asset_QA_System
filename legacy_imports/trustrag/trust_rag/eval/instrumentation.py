"""
Evaluation Instrumentation.

Instruments the system to collect metrics during query processing.
"""
import time
import logging
from typing import Dict, List, Optional, Any
from contextvars import ContextVar
from dataclasses import dataclass, field
from collections import defaultdict

from trust_rag.eval.schema import StageLatency
from trust_rag.core.monitoring import get_monitor

logger = logging.getLogger(__name__)

# Context variable for current evaluation context
_eval_context: ContextVar[Optional['EvalContext']] = ContextVar('eval_context', default=None)


@dataclass
class Span:
    """A timing span for a processing stage."""
    stage_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self):
        """Mark span as finished."""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000


@dataclass
class EvalContext:
    """Evaluation context for a single query."""
    trace_id: str
    query: str
    spans: List[Span] = field(default_factory=list)
    resource_samples: List[Dict[str, float]] = field(default_factory=list)
    
    def start_span(self, stage_name: str, metadata: Optional[Dict[str, Any]] = None) -> Span:
        """Start a new timing span."""
        span = Span(
            stage_name=stage_name,
            start_time=time.perf_counter(),
            metadata=metadata or {}
        )
        self.spans.append(span)
        return span
    
    def finish_span(self, span: Span):
        """Finish a timing span."""
        span.finish()
    
    def sample_resources(self):
        """Sample current resource usage."""
        try:
            import psutil
            process = psutil.Process()
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            self.resource_samples.append({
                "timestamp": time.time(),
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb
            })
        except Exception as e:
            logger.warning(f"Failed to sample resources: {e}")
    
    def get_stage_latencies(self) -> List[StageLatency]:
        """Get latency metrics by stage."""
        stage_latencies: Dict[str, List[float]] = defaultdict(list)
        
        for span in self.spans:
            if span.duration_ms is not None:
                stage_latencies[span.stage_name].append(span.duration_ms)
        
        result = []
        for stage_name, latencies in stage_latencies.items():
            stage_latency = StageLatency(stage_name=stage_name)
            stage_latency.calculate_percentiles(latencies)
            result.append(stage_latency)
        
        return result
    
    def get_total_latency_ms(self) -> float:
        """Get total end-to-end latency."""
        if not self.spans:
            return 0.0
        
        first_start = min(s.start_time for s in self.spans)
        last_end = max(s.end_time for s in self.spans if s.end_time is not None)
        
        if last_end:
            return (last_end - first_start) * 1000
        return 0.0


class EvalInstrumentation:
    """
    Instrumentation manager for evaluation.
    
    Provides context managers and decorators for automatic metric collection.
    """
    
    def __init__(self):
        self.active_contexts: Dict[str, EvalContext] = {}
        self.monitor = get_monitor()
    
    def start_query(self, trace_id: str, query: str) -> EvalContext:
        """Start evaluation context for a query."""
        context = EvalContext(trace_id=trace_id, query=query)
        self.active_contexts[trace_id] = context
        _eval_context.set(context)
        context.sample_resources()
        return context
    
    def finish_query(self, trace_id: str) -> Optional[EvalContext]:
        """Finish evaluation context for a query."""
        context = self.active_contexts.pop(trace_id, None)
        if context:
            context.sample_resources()
            _eval_context.set(None)
        return context
    
    def get_context(self, trace_id: Optional[str] = None) -> Optional[EvalContext]:
        """Get current evaluation context."""
        if trace_id:
            return self.active_contexts.get(trace_id)
        return _eval_context.get()
    
    def stage(self, stage_name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Context manager for a processing stage.
        
        Usage:
            with instrumentation.stage("retrieval"):
                # retrieval code
        """
        return StageContext(stage_name, metadata)
    
    def get_all_contexts(self) -> List[EvalContext]:
        """Get all active contexts."""
        return list(self.active_contexts.values())


class StageContext:
    """Context manager for a processing stage."""
    
    def __init__(self, stage_name: str, metadata: Optional[Dict[str, Any]] = None):
        self.stage_name = stage_name
        self.metadata = metadata
        self.span: Optional[Span] = None
    
    def __enter__(self):
        context = _eval_context.get()
        if context:
            self.span = context.start_span(self.stage_name, self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            context = _eval_context.get()
            if context:
                context.finish_span(self.span)
        return False


# Global instrumentation instance
_instrumentation: Optional[EvalInstrumentation] = None


def get_instrumentation() -> EvalInstrumentation:
    """Get or create global instrumentation instance."""
    global _instrumentation
    if _instrumentation is None:
        _instrumentation = EvalInstrumentation()
    return _instrumentation


def instrument_system(system_instance):
    """
    Instrument a TrustRAG system instance.
    
    This patches the system to automatically collect metrics.
    """
    from trust_rag.system import TrustRAG
    
    original_process = system_instance._process_query_internal
    
    def instrumented_process(query, risk_level, trace_id, start_time):
        """Instrumented version of process_query_internal."""
        instrumentation = get_instrumentation()
        context = instrumentation.start_query(trace_id, query)
        
        try:
            # Instrument each stage
            with instrumentation.stage("pre_judgment"):
                pre_check = system_instance.pre_gate.check(query)
                if pre_check.status == "REFUSE":
                    from trust_rag.system import SystemResult
                    return SystemResult(
                        verdict="REFUSED",
                        reasons=[pre_check.reason],
                        trace_id=trace_id
                    )
            
            with instrumentation.stage("profile"):
                profile = system_instance.profiler.profile(
                    query,
                    context={"risk_level_hint": risk_level}
                )
            
            with instrumentation.stage("route_plan"):
                plan = system_instance.planner.plan(profile)
            
            with instrumentation.stage("fast_path"):
                fast_path_result = system_instance._try_fast_path(query, profile, trace_id)
                if fast_path_result:
                    return fast_path_result
            
            with instrumentation.stage("retrieve"):
                candidates, retrieval_audit = system_instance.retrieval.retrieve(
                    query, plan, profile
                )
            
            with instrumentation.stage("judge"):
                verdict = system_instance.judgment.arbitrate(query, candidates, profile)
            
            with instrumentation.stage("generate"):
                answer_text = system_instance.renderer.generate_answer(
                    query, verdict.bindings
                )
            
            with instrumentation.stage("verify"):
                if system_instance.verification_gate:
                    proceed, adjusted_confidence, refusal_reason = \
                        system_instance.verification_gate.check(
                            answer_text, verdict.bindings, query, verdict.confidence
                        )
                    if not proceed:
                        from trust_rag.system import SystemResult
                        return SystemResult(
                            verdict="REFUSED",
                            reasons=[f"Verification failed: {refusal_reason}"],
                            trace_id=trace_id
                        )
                    final_confidence = adjusted_confidence
                else:
                    final_confidence = verdict.confidence
            
            # Build result
            result = original_process(query, risk_level, trace_id, start_time)
            
            # Add instrumentation data to verification_data
            if result.verification_data:
                result.verification_data["instrumentation"] = {
                    "stage_latencies": [
                        {
                            "stage": s.stage_name,
                            "duration_ms": s.duration_ms
                        }
                        for s in context.spans if s.duration_ms is not None
                    ],
                    "total_latency_ms": context.get_total_latency_ms()
                }
            
            return result
            
        finally:
            instrumentation.finish_query(trace_id)
    
    # Patch the method
    system_instance._process_query_internal = instrumented_process
    
    return system_instance

