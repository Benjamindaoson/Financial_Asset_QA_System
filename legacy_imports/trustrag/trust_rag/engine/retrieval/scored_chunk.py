"""
ScoredChunk: Standard output format for Retrieval Layer.
Ready for EvidenceArbitrator consumption.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

class ScoreBreakdown(BaseModel):
    """Detailed score breakdown for auditability."""
    dense: float = 0.0
    sparse: float = 0.0
    anchor: float = 0.0
    degraded_penalty: float = 0.0
    final: float = 0.0

class RetrievalAudit(BaseModel):
    """Audit trail for retrieval execution."""
    route_tier: str = ""
    route_strategy: str = ""
    recall_time_ms: float = 0.0
    fallback_triggered: bool = False
    fallback_reason: str = ""

class ScoredChunk(BaseModel):
    """
    Standard retrieval output format.
    Contains all fields needed by EvidenceArbitrator.
    """
    # Identity
    chunk_id: str
    evidence_id: str
    doc_id: str
    
    # Content
    text: str
    
    # Tier & Strategy
    tier: str  # micro, base, macro
    strategy: str  # sparse, dense, hybrid, multivector
    
    # Scores
    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    
    # Status & Degradation
    ingest_status: str = "OK"
    degraded_flags: List[str] = Field(default_factory=list)
    
    # Lineage (for arbitrator)
    source_block_ids: List[str] = Field(default_factory=list)
    section_path: List[str] = Field(default_factory=list)
    anchors: List[str] = Field(default_factory=list)
    virtual_links: Dict[str, str] = Field(default_factory=dict)
    parent_id: Optional[str] = None
    granularity: str = "composite"
    
    # Audit
    audit: RetrievalAudit = Field(default_factory=RetrievalAudit)
    
    # Extensible metadata (for evidence classification, etc.)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def score(self) -> float:
        """Compatibility with EvidenceArbitrator which expects .score"""
        return self.scores.final
    
    @property
    def chunk(self):
        """Compatibility shim for arbitrator that expects .chunk attribute"""
        return self
