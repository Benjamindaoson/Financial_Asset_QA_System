"""
RerankController: Controls optional reranking with strict budget.
Default is OFF (0 LLM calls).
"""
from typing import List, Optional, Callable
from dataclasses import dataclass
from .scored_chunk import ScoredChunk
import logging

logger = logging.getLogger(__name__)

@dataclass
class RerankConfig:
    """Rerank configuration."""
    enabled: bool = False
    max_candidates: int = 20
    top_gap_threshold: float = 0.3
    force_on_risk: bool = True

class RerankController:
    """
    Controls reranking decisions and execution.
    Default: OFF (0 LLM calls)
    """
    
    def __init__(
        self,
        config: RerankConfig = None,
        reranker_fn: Callable = None
    ):
        self.config = config or RerankConfig()
        self.reranker_fn = reranker_fn  # Injected reranker
    
    def should_rerank(
        self,
        candidates: List[ScoredChunk],
        risk_level: str = "low",
        policy_force: bool = False
    ) -> bool:
        """
        Determine if reranking should trigger.
        """
        # Policy force overrides
        if policy_force:
            return True
        
        # Disabled by config
        if not self.config.enabled:
            return False
        
        # Too few candidates
        if len(candidates) < 2:
            return False
        
        # Risk flag trigger
        if self.config.force_on_risk and risk_level in ["high", "medium"]:
            logger.info(f"Rerank triggered by risk level: {risk_level}")
            return True
        
        # Score ambiguity trigger
        if len(candidates) >= 10:
            top1 = candidates[0].scores.final
            top10 = candidates[9].scores.final
            if top1 > 0:
                gap = (top1 - top10) / top1
                if gap < self.config.top_gap_threshold:
                    logger.info(f"Rerank triggered by low score gap: {gap:.2f}")
                    return True
        
        return False
    
    def rerank(
        self,
        query: str,
        candidates: List[ScoredChunk]
    ) -> List[ScoredChunk]:
        """
        Execute reranking if reranker is available.
        """
        if not self.reranker_fn:
            logger.warning("Rerank requested but no reranker configured")
            return candidates
        
        # Bound candidates
        to_rerank = candidates[:self.config.max_candidates]
        rest = candidates[self.config.max_candidates:]
        
        try:
            reranked = self.reranker_fn(query, to_rerank)
            return reranked + rest
        except Exception as e:
            logger.error(f"Rerank failed: {e}")
            return candidates  # Fallback to original order
