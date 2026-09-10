"""
MultiRouteRecall: Executes RoutePlan routes and returns scored candidates.
"""
from typing import List, Dict, Any, Optional
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .adapter import RetrievalAdapter, RetrievalRequest, RetrievalStrategy, RawCandidate
from .scorer import HybridScorer
from .scored_chunk import ScoredChunk
from trust_rag.core.routing import RoutePlan, RouteSpec
from trust_rag.core.profile import QueryProfile, QueryIntent

logger = logging.getLogger(__name__)

class MultiRouteRecall:
    """
    Executes RoutePlan routes and returns fused candidates.
    Stage 1 (Recall) + Stage 2 (Fuse) combined.
    """
    
    MAX_TOTAL_CANDIDATES = 100  # Hard cap
    MAX_CONCURRENT_ROUTES = 3
    
    def __init__(
        self,
        adapter: RetrievalAdapter = None,
        scorer: HybridScorer = None
    ):
        self.adapter = adapter or RetrievalAdapter()
        self.scorer = scorer or HybridScorer()
    
    def recall(
        self,
        query: str,
        plan: RoutePlan,
        profile: QueryProfile = None,
        tenant_id: str = None,
        ingest_statuses: Dict[str, str] = None,
        modalities: Dict[str, str] = None
    ) -> List[ScoredChunk]:
        """
        Execute all routes in plan and return fused scored chunks.
        """
        start = time.perf_counter()
        all_candidates: List[RawCandidate] = []
        route_audits = []
        
        # Determine profile label for scoring
        profile_label = self._get_profile_label(profile)
        
        # Get anchor boost terms from profile
        boost_anchors = profile.glossary_hits if profile else []
        
        # Execute routes (parallel bounded)
        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_ROUTES) as executor:
            futures = {}
            for route in plan.routes:
                req = self._build_request(query, route, tenant_id, boost_anchors)
                future = executor.submit(self._execute_route, req)
                futures[future] = route
            
            for future in as_completed(futures):
                route = futures[future]
                try:
                    candidates = future.result()
                    all_candidates.extend(candidates)
                    route_audits.append({
                        "tier": route.tier,
                        "strategy": route.strategy.value,
                        "count": len(candidates)
                    })
                except Exception as e:
                    logger.error(f"Route {route.tier}/{route.strategy} failed: {e}")
                    route_audits.append({
                        "tier": route.tier,
                        "strategy": route.strategy.value,
                        "error": str(e)
                    })
        
        # Cap total candidates
        if len(all_candidates) > self.MAX_TOTAL_CANDIDATES:
            all_candidates = all_candidates[:self.MAX_TOTAL_CANDIDATES]
        
        # Score and fuse
        scored = self.scorer.score(
            all_candidates,
            profile_label=profile_label,
            ingest_statuses=ingest_statuses,
            modalities=modalities
        )
        
        # Add timing to audit
        total_ms = (time.perf_counter() - start) * 1000
        for chunk in scored:
            chunk.audit.recall_time_ms = total_ms
        
        logger.info(f"MultiRouteRecall: {len(scored)} candidates from {len(route_audits)} routes in {total_ms:.1f}ms")
        
        return scored
    
    def _build_request(
        self,
        query: str,
        route: RouteSpec,
        tenant_id: str,
        boost_anchors: List[str]
    ) -> RetrievalRequest:
        """Build retrieval request from route spec."""
        strategy_map = {
            "sparse": RetrievalStrategy.SPARSE,
            "dense": RetrievalStrategy.DENSE,
            "hybrid": RetrievalStrategy.HYBRID,
            "multivector": RetrievalStrategy.MULTIVECTOR
        }
        
        return RetrievalRequest(
            query=query,
            tier=route.tier,
            strategy=strategy_map.get(route.strategy.value, RetrievalStrategy.HYBRID),
            top_k=route.top_k,
            filters=route.filters,
            tenant_id=tenant_id,
            boost_anchors=boost_anchors if route.boost_anchors else None
        )
    
    def _execute_route(self, request: RetrievalRequest) -> List[RawCandidate]:
        """Execute a single route retrieval."""
        return self.adapter.search(request)
    
    def _get_profile_label(self, profile: QueryProfile) -> str:
        """Map QueryProfile intents to scoring label."""
        if not profile:
            return "default"
        
        intents = profile.intents
        if QueryIntent.FACTUAL in intents:
            if profile.numeric_sensitive:
                return "factual"
        if QueryIntent.SUMMARY in intents:
            return "summary"
        if QueryIntent.COMPARATIVE in intents:
            return "comparative"
        if profile.cross_lingual:
            return "cross_lingual"
        
        return "default"
