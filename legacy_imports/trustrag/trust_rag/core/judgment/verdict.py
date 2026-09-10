"""
Verdict and Judgment models for TrustRAG decision system.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class Verdict(BaseModel):
    """Judgment verdict with traceability."""
    status: str  # ALLOW, REFUSE, INCONCLUSIVE
    reason: str
    confidence: float
    involved_ids: List[str] = []
    bindings: Dict[str, Any] = {}

class Judgment(BaseModel):
    """Complete judgment with evidence trail."""
    verdict: Verdict
    evidence_count: int
    reasoning_steps: List[str] = []
    metadata: Dict[str, Any] = {}




