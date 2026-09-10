from typing import Dict, Any
from pydantic import BaseModel, Field

class QueryBudget(BaseModel):
    """Budget constraints for a single query."""
    max_recall: int = 50
    max_rerank: int = 20
    max_llm_calls: int = 0  # Default: 0 LLM
    max_latency_ms: int = 500
    max_tokens: int = 0

class FeatureFlags(BaseModel):
    """Feature toggles for query processing."""
    enable_llm_classifier: bool = False
    enable_rerank: bool = False  # ON_DEMAND by default
    enable_cross_modal: bool = True
    enable_glossary_rewrite: bool = True
    enable_progressive_upgrade: bool = True
    enable_conflict_protocol: bool = True
    
    # Thresholds for progressive upgrade
    confidence_threshold: float = 0.7
    top_gap_threshold: float = 0.3
    coverage_threshold: float = 0.5
    duplicate_ratio_threshold: float = 0.4
    
    # Timeouts
    llm_timeout_ms: int = 2000
    rerank_timeout_ms: int = 1000
    retrieval_timeout_ms: int = 300

# Global defaults (can be overridden per-tenant)
DEFAULT_BUDGET = QueryBudget()
DEFAULT_FLAGS = FeatureFlags()

def get_budget(tenant_id: str = None, mode: str = "default") -> QueryBudget:
    """Get budget for tenant/mode."""
    if mode == "regulatory":
        return QueryBudget(max_recall=100, max_rerank=30, max_llm_calls=1)
    elif mode == "research":
        return QueryBudget(max_recall=200, max_rerank=50, max_llm_calls=2)
    return DEFAULT_BUDGET

def get_flags(tenant_id: str = None) -> FeatureFlags:
    """Get feature flags for tenant."""
    return DEFAULT_FLAGS
