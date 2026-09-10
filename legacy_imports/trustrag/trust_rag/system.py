"""
TrustRAG Unified System Entry Point.
Enforces strict Isolation, Determinism, and Traceability.

This is the single entry point for all query processing.
All components are properly integrated with full verification.
"""
import logging
import time
import os
import json
import hashlib
from typing import Dict, Any, List, Optional, Literal, Generator
from pydantic import BaseModel, Field

from trust_rag.config import get_config, get_feature_flags, get_paths
from trust_rag.engine.performance.cache_manager import CacheManager
from trust_rag.core.profile import QueryProfiler, QueryProfile
from trust_rag.core.routing import RoutePlanner, RoutePlan
from trust_rag.engine.retrieval.pipeline import RetrievalPipeline
from trust_rag.engine.retrieval.index_loader import IndexLoader
from trust_rag.engine.retrieval.adapter import RetrievalAdapter
from trust_rag.core.judgment.guards import PreJudgmentGate
from trust_rag.core.judgment.orchestrator import JudgmentOrchestrator, ArbitratedVerdict
from trust_rag.core.judgment.validation import PostBindingVerifier, VerificationGate
from trust_rag.engine.generation.prompts import AnswerPromptGenerator
from trust_rag.core.ga_iron_laws import IronLawEnforcer
from trust_rag.core.exceptions import (
    handle_exception, TrustRAGException, IndexCorruptedException,
    IngestionFailedException, ErrorCategory, ErrorSeverity
)
from trust_rag.core.monitoring import get_monitor

logger = logging.getLogger(__name__)


class Answer(BaseModel):
    """Answer component of system result."""
    text: str
    confidence: float


class EvidenceItem(BaseModel):
    """Evidence item for traceability."""
    metric: str
    value: str
    source: str
    page: int
    evidence_id: Optional[str] = None


class SystemResult(BaseModel):
    """Unified result artifact for TrustRAG, aligned with Product Web UI."""
    verdict: Literal["VERIFIED", "REFUSED", "CONFLICT"]
    answer: Optional[Answer] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    trace_id: str
    reasons: List[str] = Field(default_factory=list)
    verification_data: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: Dict[str, bool] = Field(default_factory=dict)
    disclosure_required: bool = False


class TrustRAG:
    """
    Industrial-Grade Financial RAG System.
    The unique entry point for all query processing.
    
    Features:
    - Evidence-based answers with full traceability
    - Risk-aware arbitration with multiple evidence sources
    - Post-binding verification to prevent hallucination
    - Fast path for canonical facts
    """
    
    def __init__(
        self,
        artifact_dir: str = "artifacts",
        fact_store_path: Optional[str] = None,
        auto_load_index: bool = True
    ):
        """
        Initialize TrustRAG system.
        
        Args:
            artifact_dir: Base directory for artifacts
            fact_store_path: Path to canonical fact store (optional)
            auto_load_index: Whether to auto-load ingested documents
        """
        self.artifact_dir = artifact_dir
        self.config = get_config()
        
        # Core components
        self.profiler = QueryProfiler()
        self.planner = RoutePlanner()

        # 强制使用新的检索适配器 (BGE-M3 + pgvector) - 生产级要求
        try:
            self.retrieval_adapter = RetrievalAdapter()
            logger.info("✅ Initialized new RetrievalAdapter with BGE-M3 + pgvector")
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to initialize RetrievalAdapter: {e}")
            raise RuntimeError(f"Cannot start TrustRAG without working RetrievalAdapter: {e}")

        # Mandatory production components

        self.pre_gate = PreJudgmentGate()
        self.judgment = JudgmentOrchestrator()
        self.verifier = PostBindingVerifier()
        self.verification_gate = VerificationGate(self.verifier)
        self.renderer = AnswerPromptGenerator()
        self.iron_law_enforcer = IronLawEnforcer()  # GA IRON LAWS
        
        # Removed Shadow Arbitrator as per finance architecture
        
        # Index loader for real document retrieval
        self.index_loader = IndexLoader(
            ingestion_dir=os.path.join(artifact_dir, "ingestion")
        )
        
        # Auto-load ingested documents into retrieval adapter
        if auto_load_index:
            self._load_index()
        
        # Initialize FastPath Fact Store if path provided
        self.canonical_store = None
        if fact_store_path:
            self._init_fact_store(fact_store_path)
        elif os.path.exists(self.config.paths.fact_store_file):
            self._init_fact_store(self.config.paths.fact_store_file)
        
        # Cache Manager
        self.cache_manager = CacheManager()

        logger.info(f"TrustRAG initialized with artifact_dir={artifact_dir}")
    
    def _init_fact_store(self, path: str) -> None:
        """
        Initialize canonical fact store with error handling.
        
        Args:
            path: Path to the JSONL fact store file.
        """
        try:
            from trust_rag.core.offline.canonical_fact_store import CanonicalFactStore
            if not os.path.exists(path):
                logger.warning(f"Fact store file not found: {path}, skipping fast path")
                self.canonical_store = None
                return
            
            self.canonical_store = CanonicalFactStore(path)
            logger.info(f"Loaded canonical fact store from {path}")
        except Exception as e:
            wrapped = handle_exception(
                e,
                context={"fact_store_path": path},
                default_category=ErrorCategory.INDEX
            )
            logger.warning(f"Failed to load fact store: {wrapped.get_user_message()}")
            self.canonical_store = None
    
    def _load_index(self) -> None:
        """Load ingested documents into retrieval adapter with error handling."""
        try:
            # Use the new retrieval adapter
            stats = self.index_loader.seed_adapter(self.retrieval_adapter)
            logger.info(
                f"Loaded index: {stats.total_chunks} chunks from "
                f"{len(stats.documents)} documents"
            )
            if stats.load_errors:
                logger.warning(f"Index loading had {len(stats.load_errors)} errors")

        except Exception as e:
            wrapped = handle_exception(
                e,
                context={"ingestion_dir": self.index_loader.ingestion_dir},
                default_category=ErrorCategory.SYSTEM
            )
            logger.error(f"Failed to load index: {wrapped.get_user_message()}")
            # Don't raise - system can still work without index (will just return empty results)
    
    def refresh_index(self) -> int:
        """
        Refresh index with newly ingested documents.

        Returns:
            Number of new chunks added
        """
        return self.index_loader.refresh_adapter(self.retrieval_adapter)
    
    def process_query(
        self,
        query: str,
        risk_level: str = "medium"
    ) -> SystemResult:
        """
        Process a single query through the full pipeline.
        
        ExecutionFlow:
        1. Pre-Judgment Gate (scope check)
        2. Query Profiling
        3. Route Planning
        4. Fast Path Check (canonical facts)
        5. Evidence Retrieval
        6. Judgment Arbitration
        7. Answer Generation
        8. Post-Binding Verification
        
        Args:
            query: User query string
            risk_level: Risk level hint (low/medium/high)
            
        Returns:
            SystemResult with verdict, answer, and evidence trail
        """
        start_time = time.time()
        trace_id = f"tr_{int(start_time * 1000)}"
        
        logger.info(f"Processing query: {query[:100]}... [trace_id={trace_id}]")
        
        monitor = get_monitor()
        op_id = monitor.start_operation("query_processing", metadata={"trace_id": trace_id})
        
        try:
            # Check cache for high-frequency queries
            cache_key = f"query_res_{hashlib.md5((query + risk_level).encode()).hexdigest()}"
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                logger.info(f"Query cache hit for: {query[:50]}...")
                monitor.finish_operation(op_id, success=True, metadata={"cache_hit": True})
                return cached_result

            result = self._process_query_internal(query, risk_level, trace_id, start_time)
            
            # Cache successful results (default TTL 30 mins)
            if result.verdict == "VERIFIED":
                self.cache_manager.put(
                    cache_key, 
                    result, 
                    ttl=self.cache_manager.ttl_configs.get('query_results', 1800)
                )
            
            monitor.finish_operation(op_id, success=True)
            return result
        except TrustRAGException as e:
            monitor.finish_operation(op_id, success=False, error=e.category.value)
            logger.error(f"Query processing failed: {e.get_user_message()}")
            return SystemResult(
                verdict="REFUSED",
                reasons=[e.get_user_message()] + e.reasons if hasattr(e, 'reasons') else [],
                trace_id=trace_id,
                verification_data={
                    "error_category": e.category.value,
                    "error_severity": e.severity.value,
                    "technical_details": e.technical_details
                }
            )
        except Exception as e:
            monitor.finish_operation(op_id, success=False, error=str(e))
            wrapped = handle_exception(
                e,
                context={"query": query[:100], "risk_level": risk_level},
                default_category=ErrorCategory.SYSTEM
            )
            logger.error(f"Query processing failed: {wrapped.get_user_message()}", exc_info=True)
            return SystemResult(
                verdict="REFUSED",
                reasons=[wrapped.get_user_message()],
                trace_id=trace_id,
                verification_data={
                    "error_category": wrapped.category.value,
                    "error_severity": wrapped.severity.value,
                    "technical_details": wrapped.technical_details
                }
            )

    def process_query_stream(
        self,
        query: str,
        risk_level: str = "medium"
    ) -> Generator[str, None, None]:
        """
        Process a single query through the full pipeline with streaming updates.
        Yields SSE events (JSON strings).
        """
        start_time = time.time()
        trace_id = f"tr_{int(start_time * 1000)}"
        
        # Helper to yield event
        def yield_event(event_type: str, data: Any):
            return json.dumps({"event": event_type, "data": data})

        yield yield_event("status", "Initializing query processing...")
        
        logger.info(f"Processing query stream: {query[:100]}... [trace_id={trace_id}]")
        
        try:
            # Step 1: Pre-Judgment Gate
            yield yield_event("status", "Checking safety guidelines...")
            pre_check = self.pre_gate.check(query)
            if pre_check.status == "REFUSE":
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[pre_check.reason],
                    trace_id=trace_id
                )
                yield yield_event("result", result.model_dump())
                return
            
            # Step 2: Query Profiling
            yield yield_event("status", "Profiling query intent...")
            profile = self.profiler.profile(
                query,
                context={"risk_level_hint": risk_level}
            )
            
            # Step 3: Route Planning
            yield yield_event("status", "Planning retrieval strategy...")
            plan = self.planner.plan(profile)
            
            # Step 4: Fast Path Check (Canonical Facts)
            yield yield_event("status", "Checking fast path...")
            fast_path_result = self._try_fast_path(query, profile, trace_id)
            if fast_path_result:
                if fast_path_result.answer:
                    yield yield_event("answer_chunk", fast_path_result.answer.text)
                yield yield_event("result", fast_path_result.model_dump())
                return
            
            # Step 5: Evidence Retrieval
            yield yield_event("status", f"Retrieving evidence (top_k={plan.max_recall})...")
            
            # Temporal Prioritization (Finance specific)
            import re
            year_match = re.search(r'\b(202[0-9]|201[0-9])\b|今年|去年', query)
            if year_match:
                year_str = year_match.group(0)
                if year_str == "今年":
                    year_str = "2024"
                elif year_str == "去年":
                    year_str = "2023"
                if not plan.filters:
                    plan.filters = {}
                plan.filters["year"] = year_str
                logger.debug(f"Temporal Prioritization activated: forcing year filter {year_str}")

            try:
                # Use the new retrieval adapter (BGE-M3 + pgvector + BM25)
                candidates = self.retrieval_adapter.retrieve(
                    query=query,
                    top_k=plan.max_recall,
                    filters=plan.filters,
                    query_profile=profile.to_dict() if hasattr(profile, 'to_dict') else {}
                )
                # Convert format for downstream compatibility
                candidates = [cand.chunk for cand in candidates]
                yield yield_event("status", f"Found {len(candidates)} candidates.")
            except Exception as e:
                wrapped = handle_exception(e, default_category=ErrorCategory.RETRIEVAL)
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[f"Search failed: {wrapped.message}"],
                    trace_id=trace_id
                )
                yield yield_event("result", result.model_dump())
                return
            
            # Step 6: Judgment Arbitration
            yield yield_event("status", "Arbitrating evidence...")
            try:
                verdict = self.judgment.arbitrate(query, candidates, profile)
            except Exception as e:
                wrapped = handle_exception(e, default_category=ErrorCategory.JUDGMENT)
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[f"Arbitration failed: {wrapped.message}"],
                    trace_id=trace_id
                )
                yield yield_event("result", result.model_dump())
                return
            
            # Handle refusal/conflict
            if verdict.status == "REFUSE":
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[verdict.reason] + verdict.reasons,
                    trace_id=trace_id,
                    risk_flags=verdict.risk_flags,
                    verification_data={"arbitration": "refused"}
                )
                yield yield_event("result", result.model_dump())
                return

            if verdict.status == "CONFLICT":
                result = SystemResult(
                    verdict="CONFLICT",
                    reasons=[verdict.reason] + verdict.reasons,
                    trace_id=trace_id,
                    evidence=self._build_evidence_list(candidates, verdict.involved_ids),
                    risk_flags=verdict.risk_flags,
                    disclosure_required=True
                )
                yield yield_event("result", result.model_dump())
                return

            # GA IRON LAW ENFORCEMENT: Before generation
            core_evidence = verdict.bindings.get("core_evidence", [])
            pre_gen_violations = self.iron_law_enforcer.enforce_before_generation(
                core_evidence, query
            )
            if pre_gen_violations:
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[f"Iron law violation: {violation}" for violation in pre_gen_violations],
                    trace_id=trace_id,
                    verification_data={"iron_law_violations": pre_gen_violations}
                )
                yield yield_event("result", result.model_dump())
                return

            # Context Compression: Prevent Lost-in-the-middle
            core_evidence = verdict.bindings.get("core_evidence", [])
            if isinstance(core_evidence, list) and len(core_evidence) > 8:
                verdict.bindings["core_evidence"] = core_evidence[:4] + core_evidence[-4:]
                logger.debug(f"Context compressed from {len(core_evidence)} to 8 items to prevent lost-in-the-middle.")

            # Step 7: Answer Generation
            yield yield_event("status", "Generating answer...")
            try:
                answer_text = self.renderer.generate_answer(query, verdict.bindings)
                
                # Simulate streaming of the answer
                # In a real LLM scenario, this would come from the LLM stream
                words = answer_text.split(" ")
                for i, word in enumerate(words):
                    yield yield_event("answer_chunk", word + " ")
                    if i % 3 == 0:
                        time.sleep(0.01) # Small delay to simulate generation
                        
            except Exception as e:
                wrapped = handle_exception(e, default_category=ErrorCategory.SYSTEM)
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[f"Generation failed: {wrapped.message}"],
                    trace_id=trace_id
                )
                yield yield_event("result", result.model_dump())
                return
            
            # Step 8: Post-Binding Verification
            yield yield_event("status", "Verifying answer...")
            final_confidence = verdict.confidence
            
            if get_feature_flags().enable_post_binding_verification:
                proceed, adjusted_confidence, refusal_reason = self.verification_gate.check(
                    answer_text,
                    verdict.bindings,
                    query,
                    verdict.confidence
                )
                
                if not proceed:
                    result = SystemResult(
                        verdict="REFUSED",
                        reasons=[f"Verification failed: {refusal_reason}"],
                        trace_id=trace_id,
                        verification_data={"verification_failed": True, "reason": refusal_reason}
                    )
                    yield yield_event("result", result.model_dump())
                    return
                
                final_confidence = adjusted_confidence
            
            # Build evidence list
            evidence_list = self._build_evidence_list(candidates, verdict.involved_ids)
            
            # GA IRON LAW ENFORCEMENT: Final check
            final_violations = self.iron_law_enforcer.enforce_after_generation(
                evidence_list, answer_text, final_confidence, query
            )
            if final_violations:
                result = SystemResult(
                    verdict="REFUSED",
                    reasons=[f"Iron law violation: {violation}" for violation in final_violations],
                    trace_id=trace_id,
                    verification_data={"iron_law_violations": final_violations}
                )
                yield yield_event("result", result.model_dump())
                return

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Final Result
            final_result = SystemResult(
                verdict="VERIFIED",
                answer=Answer(text=answer_text, confidence=final_confidence),
                evidence=evidence_list,
                trace_id=trace_id,
                reasons=verdict.reasons,
                verification_data={
                    "processing_time_ms": processing_time_ms,
                    "candidates_count": len(candidates),
                    "arbitration_status": verdict.status,
                    "iron_laws_satisfied": True
                },
                risk_flags=verdict.risk_flags,
                disclosure_required=verdict.disclosure_required
            )
            yield yield_event("result", final_result.model_dump())

        except Exception as e:
            logger.error(f"Stream processing failed: {e}", exc_info=True)
            yield yield_event("error", str(e))

    def _process_query_internal(
        self,
        query: str,
        risk_level: str,
        trace_id: str,
        start_time: float
    ) -> SystemResult:
        """Internal query processing with full pipeline."""
        
        # Step 1: Pre-Judgment Gate
        pre_check = self.pre_gate.check(query)
        if pre_check.status == "REFUSE":
            return SystemResult(
                verdict="REFUSED",
                reasons=[pre_check.reason],
                trace_id=trace_id
            )
        
        # Step 2: Query Profiling
        profile = self.profiler.profile(
            query,
            context={"risk_level_hint": risk_level}
        )
        
        # Step 3: Route Planning
        plan = self.planner.plan(profile)
        
        # Step 4: Fast Path Check (Canonical Facts)
        fast_path_result = self._try_fast_path(query, profile, trace_id)
        if fast_path_result:
            return fast_path_result
        
        # Step 5: Evidence Retrieval
        # Temporal Prioritization (Finance specific)
        import re
        year_match = re.search(r'\b(202[0-9]|201[0-9])\b|今年|去年', query)
        if year_match:
            year_str = year_match.group(0)
            if year_str == "今年":
                year_str = "2024"
            elif year_str == "去年":
                year_str = "2023"
            if not plan.filters:
                plan.filters = {}
            plan.filters["year"] = year_str
            logger.debug(f"Temporal Prioritization activated: forcing year filter {year_str}")

        try:
            # Use the new retrieval adapter (BGE-M3 + pgvector + BM25)
            candidates = self.retrieval_adapter.retrieve(
                query=query,
                top_k=plan.max_recall,
                filters=plan.filters,
                query_profile=profile.to_dict() if hasattr(profile, 'to_dict') else {}
            )
            # Convert format for downstream compatibility
            candidates = [cand.chunk for cand in candidates]
            retrieval_audit = {"adapter": "new", "count": len(candidates)}

            logger.debug(f"Retrieval returned {len(candidates)} candidates")
        except Exception as e:
            wrapped = handle_exception(
                e,
                context={"query": query[:100], "plan": str(plan)},
                default_category=ErrorCategory.RETRIEVAL
            )
            logger.error(f"Retrieval failed: {wrapped.get_user_message()}")
            return SystemResult(
                verdict="REFUSED",
                reasons=[f"Search failed: {wrapped.message}"],
                trace_id=trace_id,
                verification_data={
                    "retrieval_error": True,
                    "error_details": wrapped.technical_details
                }
            )
        
        # Step 6: Judgment Arbitration
        try:
            # Use standard judgment orchestrator
            verdict = self.judgment.arbitrate(query, candidates, profile)
        except Exception as e:
            wrapped = handle_exception(
                e,
                context={"query": query[:100], "candidates_count": len(candidates)},
                default_category=ErrorCategory.JUDGMENT
            )
            logger.error(f"Arbitration failed: {wrapped.get_user_message()}")
            return SystemResult(
                verdict="REFUSED",
                reasons=[f"Arbitration failed: {wrapped.message}"],
                trace_id=trace_id,
                verification_data={
                    "arbitration_error": True,
                    "error_details": wrapped.technical_details
                }
            )
        
        # Handle refusal/conflict
        if verdict.status == "REFUSE":
            return SystemResult(
                verdict="REFUSED",
                reasons=[verdict.reason] + verdict.reasons,
                trace_id=trace_id,
                risk_flags=verdict.risk_flags,
                verification_data={"arbitration": "refused"}
            )

        if verdict.status == "CONFLICT":
            return SystemResult(
                verdict="CONFLICT",
                reasons=[verdict.reason] + verdict.reasons,
                trace_id=trace_id,
                evidence=self._build_evidence_list(candidates, verdict.involved_ids),
                risk_flags=verdict.risk_flags,
                disclosure_required=True
            )

        # GA IRON LAW ENFORCEMENT: Before generation
        core_evidence = verdict.bindings.get("core_evidence", [])
        pre_gen_violations = self.iron_law_enforcer.enforce_before_generation(
            core_evidence, query
        )
        if pre_gen_violations:
            return SystemResult(
                verdict="REFUSED",
                reasons=[f"Iron law violation: {violation}" for violation in pre_gen_violations],
                trace_id=trace_id,
                verification_data={"iron_law_violations": pre_gen_violations}
            )

        # Context Compression: Prevent Lost-in-the-middle
        core_evidence = verdict.bindings.get("core_evidence", [])
        if isinstance(core_evidence, list) and len(core_evidence) > 8:
            verdict.bindings["core_evidence"] = core_evidence[:4] + core_evidence[-4:]
            logger.debug(f"Context compressed from {len(core_evidence)} to 8 items to prevent lost-in-the-middle.")

        # Step 7: Answer Generation
        try:
            answer_text = self.renderer.generate_answer(query, verdict.bindings)
        except Exception as e:
            wrapped = handle_exception(
                e,
                context={"query": query[:100], "bindings_keys": list(verdict.bindings.keys())},
                default_category=ErrorCategory.SYSTEM
            )
            logger.error(f"Answer generation failed: {wrapped.get_user_message()}")
            return SystemResult(
                verdict="REFUSED",
                reasons=[f"Generation failed: {wrapped.message}"],
                trace_id=trace_id,
                verification_data={
                    "generation_error": True,
                    "error_details": wrapped.technical_details
                }
            )
        
        # Step 8: Post-Binding Verification
        if get_feature_flags().enable_post_binding_verification:
            proceed, adjusted_confidence, refusal_reason = self.verification_gate.check(
                answer_text,
                verdict.bindings,
                query,
                verdict.confidence
            )
            
            if not proceed:
                return SystemResult(
                    verdict="REFUSED",
                    reasons=[f"Verification failed: {refusal_reason}"],
                    trace_id=trace_id,
                    verification_data={"verification_failed": True, "reason": refusal_reason}
                )
            
            final_confidence = adjusted_confidence
        else:
            final_confidence = verdict.confidence
        
        # Build evidence list
        evidence_list = self._build_evidence_list(candidates, verdict.involved_ids)
        
        # GA IRON LAW ENFORCEMENT: Final check after all processing
        final_violations = self.iron_law_enforcer.enforce_after_generation(
            evidence_list, answer_text, final_confidence, query
        )
        if final_violations:
            return SystemResult(
                verdict="REFUSED",
                reasons=[f"Iron law violation: {violation}" for violation in final_violations],
                trace_id=trace_id,
                verification_data={"iron_law_violations": final_violations}
            )

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        return SystemResult(
            verdict="VERIFIED",
            answer=Answer(text=answer_text, confidence=final_confidence),
            evidence=evidence_list,
            trace_id=trace_id,
            reasons=verdict.reasons,
            verification_data={
                "processing_time_ms": processing_time_ms,
                "candidates_count": len(candidates),
                "arbitration_status": verdict.status,
                "iron_laws_satisfied": True
            },
            risk_flags=verdict.risk_flags,
            disclosure_required=verdict.disclosure_required
        )
    
    def _try_fast_path(
        self,
        query: str,
        profile: QueryProfile,
        trace_id: str
    ) -> Optional[SystemResult]:
        """
        Try fast path lookup in canonical fact store.
        
        Returns:
            SystemResult if fast path hit, None otherwise
        """
        if not self.canonical_store:
            return None
        
        # Extract query parameters
        query_lower = query.lower()
        
        # Identify metric
        metric = None
        metric_keywords = self.config.fast_path.metric_keywords
        
        for m, keywords in metric_keywords.items():
            if any(kw in query_lower for kw in keywords):
                metric = m
                break
        
        if not metric:
            return None
        
        # Identify entity
        entity = None
        entity_keywords = self.config.fast_path.entity_keywords
        
        for e, keywords in entity_keywords.items():
            if any(kw in query_lower for kw in keywords):
                entity = e
                break
        
        if not entity:
            return None
        
        # Identify period
        period = None
        period_patterns = [
            (r'FY\s*(\d{4})', lambda m: f"FY{m.group(1)}"),
            (r'fiscal\s*(?:year)?\s*(\d{4})', lambda m: f"FY{m.group(1)}"),
            (r'Q([1-4])\s*(\d{4})', lambda m: f"Q{m.group(1)} {m.group(2)}"),
        ]
        
        import re
        for pattern, formatter in period_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                period = formatter(match)
                break
        
        if not period:
            period = "FY2023"  # Default
        
        # Lookup in fact store
        fact = self.canonical_store.lookup(metric, period, entity=entity)
        
        if fact:
            return SystemResult(
                verdict="VERIFIED",
                answer=Answer(
                    text=f"{entity}'s {metric.replace('_', ' ')} for {period} was {fact.value} {fact.unit}.",
                    confidence=1.0
                ),
                evidence=[EvidenceItem(
                    metric=metric,
                    value=f"{fact.value} {fact.unit}",
                    source=f"{entity} {period} Filing",
                    page=1
                )],
                trace_id=trace_id,
                reasons=["FastPath: Canonical fact match"],
                verification_data={"fast_path": True, "source_ids": fact.source_evidence_ids}
            )
        
        # Entity exists but no data
        if entity:
            logger.debug(f"Fast path: No data for {entity}/{metric}/{period}")
        
        return None
    
    def _build_evidence_list(
        self,
        candidates: List[Any],
        involved_ids: List[str]
    ) -> List[EvidenceItem]:
        """Build evidence list from candidates for result."""
        evidence_list = []
        
        for cand in candidates:
            chunk = getattr(cand, 'chunk', cand)
            evidence_id = getattr(chunk, 'evidence_id', None)
            
            if evidence_id and evidence_id in involved_ids:
                # Extract metadata
                doc_id = getattr(chunk, 'doc_id', 'Unknown Source')
                
                # Try to get page from metadata
                page = 0
                if hasattr(chunk, 'metadata') and chunk.metadata:
                    page = chunk.metadata.get('page_number', 0)
                
                # Extract a value snippet
                text = getattr(chunk, 'text', '')
                value_snippet = text[:100] if text else "Evidence chunk"
                
                evidence_list.append(EvidenceItem(
                    metric="extracted_fact",
                    value=value_snippet,
                    source=doc_id,
                    page=page,
                    evidence_id=evidence_id
                ))
        
        return evidence_list[:5]  # Limit to top 5
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get current index statistics.
        
        Returns:
            Dictionary containing metrics like total chunks, documents, and distribution.
        """
        return self.index_loader.get_stats()
    
    def ingest_document(
        self,
        file_path: str,
        doc_id: Optional[str] = None,
        profile: str = "generic"
    ) -> Dict[str, Any]:
        """
        Ingest a document and update the index.
        
        Args:
            file_path: Path to document file
            doc_id: Optional document ID
            profile: Ingest profile name
            
        Returns:
            Ingest result dictionary
        """
        from trust_rag.engine.ingest.pipeline import IngestPipeline
        
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Document file not found: {file_path}")
            
            pipeline = IngestPipeline(
                output_dir=os.path.join(self.artifact_dir, "ingestion")
            )
            
            result = pipeline.ingest(file_path, doc_id=doc_id, ingest_profile=profile)
            
            # Refresh index with new document
            try:
                new_chunks = self.refresh_index()
                logger.info(f"Index refreshed with {new_chunks} new chunks")
            except Exception as e:
                wrapped = handle_exception(e, default_category=ErrorCategory.INDEX)
                logger.warning(f"Index refresh failed after ingestion: {wrapped.message}")
                new_chunks = 0
            
            return {
                "doc_id": result.doc_id,
                "status": result.ingest_status,
                "chunks_count": len(result.chunks),
                "new_index_chunks": new_chunks,
                "errors": result.errors
            }
        except FileNotFoundError as e:
            raise IngestionFailedException(
                file_path=file_path,
                reason=f"File not found: {str(e)}"
            )
        except Exception as e:
            wrapped = handle_exception(
                e,
                context={"file_path": file_path, "profile": profile},
                default_category=ErrorCategory.INGESTION
            )
            raise IngestionFailedException(
                file_path=file_path,
                reason=f"Ingestion process error: {wrapped.message}"
            )
