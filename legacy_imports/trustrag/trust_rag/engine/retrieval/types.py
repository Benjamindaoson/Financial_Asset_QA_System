from __future__ import annotations

from enum import Enum
from typing import List, Dict, Optional, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from trust_rag.core.evidence import Provenance

class IntentType(str, Enum):
    FACT_CHECK = "fact_check"
    COMPARISON = "comparison"
    NUMERIC_JUDGMENT = "numeric_judgment"
    POLICY_MATCH = "policy_match"
    OPEN_QUERY = "open_query"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class RetrievalBudget(BaseModel):
    max_chunks: int
    min_evidence_units: int
    per_index_cap: int

class RetrievalHit(BaseModel):
    chunk_id: str
    index_type: str
    score: float
    text: str
    provenance: List[Provenance]
    metadata: Dict[str, Any] = Field(default_factory=dict)

class NumericSignature(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    type: Literal["currency", "percent", "date", "duration", "unit"]
    value: float | str # str for dates if regex extraction is loose
    unit: Optional[str] = None
    raw: str
    span: tuple[int, int]

class IndexEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    entry_id: str
    index_type: Literal["dense_text", "sparse_bm25", "table_row", "numeric_signature"]
    chunk_id: str
    chunk_policy_id: str
    doc_id: str
    doc_version: str = "latest"
    text: str
    
    # Optional Payloads
    vector: Optional[List[float]] = None
    tokens: Optional[List[str]] = None
    table: Optional[Dict[str, Any]] = None
    numeric_sig: Optional[List[NumericSignature]] = None
    
    # Audit
    signals: Dict[str, Any] = Field(default_factory=dict)
    provenance: List[Provenance] = Field(default_factory=list)

class RetrievalDecision(BaseModel):
    intent: IntentType
    risk_level: RiskLevel
    indexes_active: List[str]
    budget: RetrievalBudget
    reason: str

class RetrievalTrace(BaseModel):
    trace_id: str
    query: str
    decision: RetrievalDecision
    hits_summary: Dict[str, int]
    sufficiency_check: Dict[str, Any]
    steps: List[Dict[str, Any]] = Field(default_factory=list)
