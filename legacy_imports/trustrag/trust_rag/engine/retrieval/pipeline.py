"""
RetrievalPipeline: Unified 4-stage retrieval pipeline.
Recall → Fuse → Rerank (optional) → Converge
"""
from typing import List, Dict, Any, Optional, Tuple
import logging

from .adapter import RetrievalAdapter
from .scorer import HybridScorer
from .recall import MultiRouteRecall
from .rerank import RerankController, RerankConfig
from .scored_chunk import ScoredChunk
from trust_rag.core.routing import RoutePlan
from trust_rag.core.profile import QueryProfile

logger = logging.getLogger(__name__)

class RetrievalPipeline:
    """
    Unified retrieval pipeline for TrustRAG.
    Implements: Recall → Fuse → Rerank(optional) → Converge
    """
    
    def __init__(
        self,
        adapter: RetrievalAdapter = None,
        scorer: HybridScorer = None,
        rerank_controller: RerankController = None
    ):
        self.adapter = adapter or RetrievalAdapter()
        self.scorer = scorer or HybridScorer()
        self.recall = MultiRouteRecall(adapter=self.adapter, scorer=self.scorer)
        self.rerank_controller = rerank_controller or RerankController()
    
    def retrieve(
        self,
        query: str,
        plan: RoutePlan,
        profile: QueryProfile = None,
        tenant_id: str = None,
        ingest_statuses: Dict[str, str] = None,
        modalities: Dict[str, str] = None
    ) -> Tuple[List[ScoredChunk], Dict[str, Any]]:
        """
        Execute full retrieval pipeline.
        
        Returns:
            Tuple of (scored_chunks, audit_info)
        """
        audit = {
            "stages_executed": [],
            "rerank_triggered": False,
            "fallbacks": []
        }
        
        # Stage 1+2: Recall + Fuse
        audit["stages_executed"].append("recall")
        candidates = self.recall.recall(
            query=query,
            plan=plan,
            profile=profile,
            tenant_id=tenant_id,
            ingest_statuses=ingest_statuses,
            modalities=modalities
        )
        audit["recall_count"] = len(candidates)
        
        # Stage 3: Rerank (if triggered)
        risk_level = profile.risk_level.value if profile else "low"
        policy_force = plan.rerank_policy.value == "force"
        
        if self.rerank_controller.should_rerank(candidates, risk_level, policy_force):
            audit["stages_executed"].append("rerank")
            audit["rerank_triggered"] = True
            candidates = self.rerank_controller.rerank(query, candidates)
        
        # Stage 4: Ready for Converge (EvidenceArbitrator)
        audit["stages_executed"].append("converge_ready")
        audit["final_count"] = len(candidates)
        
        return candidates, audit
    
    def retrieve_safe(
        self,
        query: str,
        plan: RoutePlan,
        **kwargs
    ) -> Tuple[List[ScoredChunk], Dict[str, Any]]:
        """
        Retrieve with full error handling and fallbacks.
        """
        try:
            return self.retrieve(query, plan, **kwargs)
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return [], {
                "error": str(e),
                "stages_executed": [],
                "fallback": "empty_result"
            }
