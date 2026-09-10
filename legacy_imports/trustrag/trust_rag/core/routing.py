"""
RoutePlanner: Policy-driven, progressive routing.
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from .profile import QueryProfile, QueryIntent, RiskLevel, Language
from .flags import QueryBudget, FeatureFlags, get_budget, get_flags

class RetrievalStrategy(str, Enum):
    SPARSE = "sparse"
    DENSE = "dense"
    HYBRID = "hybrid"

class RerankPolicy(str, Enum):
    OFF = "off"
    ON_DEMAND = "on_demand"
    FORCE = "force"

class ConflictPolicy(str, Enum):
    OFF = "off"
    ON = "on"
    FORCE = "force"

class CrossModalPolicy(str, Enum):
    OFF = "off"
    ON_DEMAND = "on_demand"
    FORCE = "force"

class DisclosurePolicy(str, Enum):
    NEVER = "never"
    WHEN_DEGRADED = "when_degraded"
    WHEN_CONFLICT = "when_conflict"
    ALWAYS = "always"

@dataclass
class RouteSpec:
    """Single retrieval route specification."""
    tier: str  # micro, base, macro
    strategy: RetrievalStrategy
    top_k: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)
    boost_anchors: bool = False
    priority: int = 0  # Higher = execute first

@dataclass
class RoutePlan:
    """Complete routing plan for a query."""
    routes: List[RouteSpec] = field(default_factory=list)
    rerank_policy: RerankPolicy = RerankPolicy.OFF
    conflict_policy: ConflictPolicy = ConflictPolicy.ON
    cross_modal_policy: CrossModalPolicy = CrossModalPolicy.OFF
    disclosure_policy: DisclosurePolicy = DisclosurePolicy.WHEN_CONFLICT
    budget: QueryBudget = field(default_factory=QueryBudget)
    stage: int = 0  # Progressive routing stage
    upgrade_triggers: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for audit logging."""
        return {
            "routes": [
                {"tier": r.tier, "strategy": r.strategy.value, "top_k": r.top_k, 
                 "filters": r.filters, "boost_anchors": r.boost_anchors}
                for r in self.routes
            ],
            "rerank_policy": self.rerank_policy.value,
            "conflict_policy": self.conflict_policy.value,
            "cross_modal_policy": self.cross_modal_policy.value,
            "disclosure_policy": self.disclosure_policy.value,
            "budget": {
                "max_recall": self.budget.max_recall,
                "max_rerank": self.budget.max_rerank,
                "max_llm_calls": self.budget.max_llm_calls
            },
            "stage": self.stage,
            "upgrade_triggers": self.upgrade_triggers
        }

# Policy Registry
class PolicyRegistry:
    """Extensible policy registry for domain/tenant/mode policies."""
    
    def __init__(self):
        self._domain_policies: Dict[str, Callable] = {}
        self._tenant_policies: Dict[str, Callable] = {}
        self._mode_policies: Dict[str, Callable] = {}
    
    def register_domain(self, domain: str, policy_fn: Callable):
        self._domain_policies[domain] = policy_fn
    
    def register_tenant(self, tenant_id: str, policy_fn: Callable):
        self._tenant_policies[tenant_id] = policy_fn
    
    def register_mode(self, mode: str, policy_fn: Callable):
        self._mode_policies[mode] = policy_fn
    
    def get_domain_policy(self, domain: str) -> Optional[Callable]:
        return self._domain_policies.get(domain)
    
    def get_tenant_policy(self, tenant_id: str) -> Optional[Callable]:
        return self._tenant_policies.get(tenant_id)
    
    def get_mode_policy(self, mode: str) -> Optional[Callable]:
        return self._mode_policies.get(mode)

# Default policies
def finance_policy(plan: RoutePlan, profile: QueryProfile) -> RoutePlan:
    """Finance domain: stricter numeric handling."""
    if profile.numeric_sensitive:
        plan.conflict_policy = ConflictPolicy.FORCE
        plan.disclosure_policy = DisclosurePolicy.ALWAYS
    return plan

def legal_policy(plan: RoutePlan, profile: QueryProfile) -> RoutePlan:
    """Legal domain: always disclose, no shortcuts."""
    plan.disclosure_policy = DisclosurePolicy.ALWAYS
    plan.conflict_policy = ConflictPolicy.FORCE
    return plan

def regulatory_mode_policy(plan: RoutePlan, profile: QueryProfile) -> RoutePlan:
    """Regulatory mode: conservative, full audit."""
    plan.budget.max_recall = 100
    plan.conflict_policy = ConflictPolicy.FORCE
    plan.disclosure_policy = DisclosurePolicy.ALWAYS
    return plan

# Global registry with defaults
POLICY_REGISTRY = PolicyRegistry()
POLICY_REGISTRY.register_domain("finance", finance_policy)
POLICY_REGISTRY.register_domain("legal", legal_policy)
POLICY_REGISTRY.register_mode("regulatory", regulatory_mode_policy)

class RoutePlanner:
    """
    Creates routing plans based on QueryProfile.
    Policy-driven, progressive, low-cost by default.
    """
    
    def __init__(self, registry: PolicyRegistry = None, flags: FeatureFlags = None):
        self.registry = registry or POLICY_REGISTRY
        self.flags = flags or get_flags()
    
    def plan(
        self, 
        profile: QueryProfile, 
        tenant_id: str = None,
        domain: str = None,
        mode: str = None,
        ingest_status: str = "OK"
    ) -> RoutePlan:
        """
        Generate routing plan from profile.
        """
        plan = RoutePlan()
        plan.budget = get_budget(tenant_id, mode)
        
        # Stage 0: Default fast path
        routes = self._build_routes(profile, ingest_status)
        plan.routes = routes
        
        # Set policies based on profile
        plan = self._apply_profile_policies(plan, profile)
        
        # Degraded mode: conservative
        if ingest_status == "DEGRADED":
            plan = self._apply_degraded_mode(plan)
        
        # Apply domain policy
        if domain:
            policy_fn = self.registry.get_domain_policy(domain)
            if policy_fn:
                plan = policy_fn(plan, profile)
        
        # Apply mode policy
        if mode:
            policy_fn = self.registry.get_mode_policy(mode)
            if policy_fn:
                plan = policy_fn(plan, profile)
        
        # Apply tenant policy
        if tenant_id:
            policy_fn = self.registry.get_tenant_policy(tenant_id)
            if policy_fn:
                plan = policy_fn(plan, profile)
        
        return plan
    
    def _build_routes(self, profile: QueryProfile, ingest_status: str) -> List[RouteSpec]:
        """Build retrieval routes based on profile."""
        routes = []
        
        # Conservative: FACTUAL or HIGH risk → dual path
        is_conservative = (
            QueryIntent.FACTUAL in profile.intents or 
            profile.risk_level == RiskLevel.HIGH or
            profile.numeric_sensitive
        )
        
        if is_conservative:
            # FACT path: MICRO sparse + BASE hybrid
            routes.append(RouteSpec(
                tier="micro", 
                strategy=RetrievalStrategy.SPARSE, 
                top_k=15,
                boost_anchors=bool(profile.glossary_hits),
                priority=1
            ))
            routes.append(RouteSpec(
                tier="base", 
                strategy=RetrievalStrategy.HYBRID, 
                top_k=10,
                priority=0
            ))
        else:
            # Fast path: BASE only
            routes.append(RouteSpec(
                tier="base",
                strategy=RetrievalStrategy.SPARSE if profile.confidence > 0.8 else RetrievalStrategy.HYBRID,
                top_k=10,
                priority=0
            ))
        
        # SUMMARY intent: add MACRO
        if QueryIntent.SUMMARY in profile.intents:
            routes.append(RouteSpec(
                tier="macro",
                strategy=RetrievalStrategy.DENSE,
                top_k=5,
                priority=-1  # Lower priority
            ))
        
        # Cross-lingual: boost anchors on all routes
        if profile.cross_lingual and profile.glossary_hits:
            for r in routes:
                r.boost_anchors = True
        
        # Degraded: skip MACRO multivector
        if ingest_status == "DEGRADED":
            routes = [r for r in routes if r.tier != "macro" or r.strategy != RetrievalStrategy.DENSE]
        
        return routes
    
    def _apply_profile_policies(self, plan: RoutePlan, profile: QueryProfile) -> RoutePlan:
        """Set policies based on profile signals."""
        
        # Rerank: only if low confidence or ambiguous
        if profile.confidence < self.flags.confidence_threshold:
            plan.rerank_policy = RerankPolicy.ON_DEMAND
            plan.upgrade_triggers.append("low_confidence")
        
        # Cross-modal: if numeric + multimodal hints
        if profile.numeric_sensitive and profile.multi_modal:
            plan.cross_modal_policy = CrossModalPolicy.ON_DEMAND
            plan.upgrade_triggers.append("numeric_multimodal")
        
        # Conflict: HIGH risk forces
        if profile.risk_level == RiskLevel.HIGH:
            plan.conflict_policy = ConflictPolicy.FORCE
            plan.disclosure_policy = DisclosurePolicy.ALWAYS
        
        return plan
    
    def _apply_degraded_mode(self, plan: RoutePlan) -> RoutePlan:
        """Conservative mode for DEGRADED ingest status."""
        plan.rerank_policy = RerankPolicy.OFF
        plan.budget.max_llm_calls = 0
        plan.disclosure_policy = DisclosurePolicy.ALWAYS
        plan.upgrade_triggers.append("ingest_degraded")
        return plan
