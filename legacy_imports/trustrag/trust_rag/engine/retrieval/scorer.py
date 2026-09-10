"""
HybridScorer: Fuses dense/sparse/anchor scores with degraded penalties.
Produces final score based on QueryProfile labels.
"""
from typing import List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from .scored_chunk import ScoredChunk, ScoreBreakdown, RetrievalAudit

if TYPE_CHECKING:
    from .adapter import RawCandidate

@dataclass
class ScoringWeights:
    """Weights for score fusion."""
    w_dense: float = 0.4
    w_sparse: float = 0.4
    w_anchor: float = 0.2

# Profile-based weight presets
WEIGHT_PRESETS = {
    "factual": ScoringWeights(w_dense=0.2, w_sparse=0.5, w_anchor=0.3),
    "summary": ScoringWeights(w_dense=0.6, w_sparse=0.2, w_anchor=0.2),
    "cross_lingual": ScoringWeights(w_dense=0.3, w_sparse=0.3, w_anchor=0.4),
    "comparative": ScoringWeights(w_dense=0.4, w_sparse=0.4, w_anchor=0.2),
    "default": ScoringWeights(w_dense=0.4, w_sparse=0.4, w_anchor=0.2),
}

# Modality trust for degraded penalty
MODALITY_TRUST = {
    "text_native": 1.0,
    "table_native": 0.95,
    "text_ocr": 0.70,
    "table_ocr": 0.65,
    "chart": 0.40,
}

# Ingest status penalties
STATUS_PENALTIES = {
    "OK": 0.0,
    "DEGRADED": 0.3,
    "FAILED": 0.7,
}

class HybridScorer:
    """
    Fuses retrieval scores into a single final score.
    Weights are selected by QueryProfile labels (no LLM).
    """
    
    def __init__(self):
        self.weight_presets = WEIGHT_PRESETS
    
    def score(
        self,
        candidates: List["RawCandidate"],
        profile_label: str = "default",
        ingest_statuses: Dict[str, str] = None,
        modalities: Dict[str, str] = None
    ) -> List[ScoredChunk]:
        """
        Score and convert raw candidates to ScoredChunks.
        
        Args:
            candidates: Raw candidates from retrieval
            profile_label: Query profile label for weight selection
            ingest_statuses: Map of evidence_id -> ingest_status
            modalities: Map of evidence_id -> modality
        """
        ingest_statuses = ingest_statuses or {}
        modalities = modalities or {}
        
        # Select weights
        weights = self.weight_presets.get(profile_label, self.weight_presets["default"])
        
        # Calculate ranks for RRF (Reciprocal Rank Fusion)
        k = 60
        dense_sorted = sorted(candidates, key=lambda x: x.dense_score, reverse=True)
        sparse_sorted = sorted(candidates, key=lambda x: x.sparse_score, reverse=True)
        anchor_sorted = sorted(candidates, key=lambda x: x.anchor_score, reverse=True)
        
        dense_ranks = {c.chunk_id: i + 1 for i, c in enumerate(dense_sorted) if c.dense_score > 0}
        sparse_ranks = {c.chunk_id: i + 1 for i, c in enumerate(sparse_sorted) if c.sparse_score > 0}
        anchor_ranks = {c.chunk_id: i + 1 for i, c in enumerate(anchor_sorted) if c.anchor_score > 0}
        
        scored = []
        for c in candidates:
            # Normalize scores to [0, 1] for breakdown display
            s_dense = self._normalize(c.dense_score)
            s_sparse = self._normalize(c.sparse_score)
            s_anchor = self._normalize(c.anchor_score)
            
            # RRF Ranks
            r_dense = dense_ranks.get(c.chunk_id, 0)
            r_sparse = sparse_ranks.get(c.chunk_id, 0)
            r_anchor = anchor_ranks.get(c.chunk_id, 0)
            
            # Compute base score using RRF
            # Max possible score for rank 1 is 1/(k+1) ~= 0.016. We multiply by (k+1) to scale max back to 1.0.
            s_base = 0.0
            if r_dense > 0:
                s_base += weights.w_dense * (1.0 / (k + r_dense))
            if r_sparse > 0:
                s_base += weights.w_sparse * (1.0 / (k + r_sparse))
            if r_anchor > 0:
                s_base += weights.w_anchor * (1.0 / (k + r_anchor))
            
            s_base = s_base * (k + 1)
            
            # Compute degraded penalty
            p_degraded = self._compute_penalty(
                c.evidence_id,
                ingest_statuses,
                modalities,
                c.metadata
            )
            
            # Final score
            s_final = s_base * (1 - p_degraded)
            
            # Build ScoredChunk
            metadata = c.metadata or {}
            degraded_flags = []
            if p_degraded > 0:
                degraded_flags.append(f"penalty_{p_degraded:.2f}")
            
            scored.append(ScoredChunk(
                chunk_id=c.chunk_id,
                evidence_id=c.evidence_id,
                doc_id=c.doc_id,
                text=c.text,
                tier=c.tier,
                strategy=c.strategy,
                scores=ScoreBreakdown(
                    dense=s_dense,
                    sparse=s_sparse,
                    anchor=s_anchor,
                    degraded_penalty=p_degraded,
                    final=s_final
                ),
                ingest_status=ingest_statuses.get(c.evidence_id, "OK"),
                degraded_flags=degraded_flags,
                source_block_ids=metadata.get("source_block_ids", []),
                section_path=metadata.get("section_path", []),
                anchors=metadata.get("anchors", []),
                virtual_links=metadata.get("virtual_links", {}),
                parent_id=metadata.get("parent_id"),
                granularity=metadata.get("granularity", "composite"),
                audit=RetrievalAudit(
                    route_tier=c.tier,
                    route_strategy=c.strategy
                )
            ))
        
        # Sort by final score descending
        scored.sort(key=lambda x: x.scores.final, reverse=True)
        return scored
    
    def _normalize(self, score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Normalize score to [0, 1]."""
        if score <= min_val:
            return 0.0
        if score >= max_val:
            return 1.0
        return (score - min_val) / (max_val - min_val)
    
    def _compute_penalty(
        self,
        evidence_id: str,
        ingest_statuses: Dict[str, str],
        modalities: Dict[str, str],
        metadata: Dict[str, Any]
    ) -> float:
        """Compute degraded penalty based on status and modality."""
        metadata = metadata or {}  # Handle None
        penalty = 0.0
        
        # Ingest status penalty
        status = ingest_statuses.get(evidence_id, "OK")
        penalty += STATUS_PENALTIES.get(status, 0.0)
        
        # Modality penalty
        modality = modalities.get(evidence_id) or metadata.get("modality", "text_native")
        trust = MODALITY_TRUST.get(modality, 0.7)
        modality_penalty = 1.0 - trust
        penalty += modality_penalty * 0.3  # Weighted contribution
        
        # Parsing anomaly penalty (from preflight)
        if metadata and metadata.get("anomaly_score", 0) > 0.1:
            penalty += metadata.get("anomaly_score", 0) * 0.2
        
        return min(penalty, 0.9)  # Cap at 90% penalty
