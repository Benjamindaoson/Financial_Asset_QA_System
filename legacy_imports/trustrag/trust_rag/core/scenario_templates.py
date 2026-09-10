"""
High-Risk/High-Value Scenario Templates.

Provides pre-configured risk control parameters and arbitration rules
for different business scenarios (medical, legal, financial).
"""
from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

from trust_rag.config import TrustRAGConfig, get_config


class ScenarioType(str, Enum):
    """Supported scenario types."""
    FINANCIAL = "financial"
    MEDICAL = "medical"
    LEGAL = "legal"
    REGULATORY = "regulatory"
    RESEARCH = "research"
    GENERIC = "generic"


class ScenarioConfig(BaseModel):
    """Configuration for a specific scenario."""
    scenario_name: str
    scenario_type: ScenarioType
    
    # Risk control parameters
    min_confidence_threshold: float = 0.7
    require_multiple_sources: bool = False
    min_source_count: int = 1
    allow_ocr_for_numeric: bool = False
    require_native_text: bool = False
    
    # Arbitration rules
    conflict_resolution: str = "refuse"  # refuse, disclose, highest_authority
    evidence_quality_requirement: str = "high"  # low, medium, high
    
    # Source authority weights (override default)
    source_authority_weights: Dict[str, float] = Field(default_factory=dict)
    
    # Custom thresholds
    custom_thresholds: Dict[str, Any] = Field(default_factory=dict)
    
    # Disclosure requirements
    always_disclose_conflicts: bool = True
    always_disclose_ocr: bool = True
    always_disclose_degraded: bool = True


# Pre-configured scenario templates
SCENARIO_TEMPLATES: Dict[ScenarioType, ScenarioConfig] = {
    ScenarioType.FINANCIAL: ScenarioConfig(
        scenario_name="Financial Reporting",
        scenario_type=ScenarioType.FINANCIAL,
        min_confidence_threshold=0.85,
        require_multiple_sources=True,
        min_source_count=2,
        allow_ocr_for_numeric=False,
        require_native_text=True,
        conflict_resolution="refuse",
        evidence_quality_requirement="high",
        source_authority_weights={
            "annual_report": 1.0,
            "audit": 0.95,
            "regulatory_filing": 0.9,
            "news": 0.3,
            "draft": 0.2
        },
        always_disclose_conflicts=True,
        always_disclose_ocr=True,
        always_disclose_degraded=True
    ),
    
    ScenarioType.MEDICAL: ScenarioConfig(
        scenario_name="Medical Documentation",
        scenario_type=ScenarioType.MEDICAL,
        min_confidence_threshold=0.90,
        require_multiple_sources=True,
        min_source_count=2,
        allow_ocr_for_numeric=False,
        require_native_text=True,
        conflict_resolution="refuse",
        evidence_quality_requirement="high",
        source_authority_weights={
            "peer_reviewed": 1.0,
            "clinical_trial": 0.95,
            "medical_journal": 0.9,
            "textbook": 0.85,
            "guideline": 0.8,
            "web": 0.3
        },
        always_disclose_conflicts=True,
        always_disclose_ocr=True,
        always_disclose_degraded=True
    ),
    
    ScenarioType.LEGAL: ScenarioConfig(
        scenario_name="Legal Documentation",
        scenario_type=ScenarioType.LEGAL,
        min_confidence_threshold=0.90,
        require_multiple_sources=False,
        min_source_count=1,
        allow_ocr_for_numeric=False,
        require_native_text=True,
        conflict_resolution="refuse",
        evidence_quality_requirement="high",
        source_authority_weights={
            "statute": 1.0,
            "case_law": 0.95,
            "regulation": 0.9,
            "contract": 0.85,
            "legal_opinion": 0.7,
            "web": 0.2
        },
        always_disclose_conflicts=True,
        always_disclose_ocr=True,
        always_disclose_degraded=True
    ),
    
    ScenarioType.REGULATORY: ScenarioConfig(
        scenario_name="Regulatory Compliance",
        scenario_type=ScenarioType.REGULATORY,
        min_confidence_threshold=0.85,
        require_multiple_sources=True,
        min_source_count=2,
        allow_ocr_for_numeric=False,
        require_native_text=True,
        conflict_resolution="refuse",
        evidence_quality_requirement="high",
        source_authority_weights={
            "regulation": 1.0,
            "guidance": 0.9,
            "official_interpretation": 0.85,
            "industry_standard": 0.7,
            "web": 0.3
        },
        always_disclose_conflicts=True,
        always_disclose_ocr=True,
        always_disclose_degraded=True
    ),
    
    ScenarioType.RESEARCH: ScenarioConfig(
        scenario_name="Research & Analysis",
        scenario_type=ScenarioType.RESEARCH,
        min_confidence_threshold=0.70,
        require_multiple_sources=False,
        min_source_count=1,
        allow_ocr_for_numeric=True,
        require_native_text=False,
        conflict_resolution="disclose",
        evidence_quality_requirement="medium",
        source_authority_weights={
            "peer_reviewed": 1.0,
            "academic_paper": 0.9,
            "research_report": 0.8,
            "web": 0.5
        },
        always_disclose_conflicts=False,
        always_disclose_ocr=False,
        always_disclose_degraded=False
    ),
    
    ScenarioType.GENERIC: ScenarioConfig(
        scenario_name="Generic",
        scenario_type=ScenarioType.GENERIC,
        min_confidence_threshold=0.70,
        require_multiple_sources=False,
        min_source_count=1,
        allow_ocr_for_numeric=True,
        require_native_text=False,
        conflict_resolution="disclose",
        evidence_quality_requirement="medium"
    )
}


class ScenarioManager:
    """
    Manages scenario configurations and applies them to system config.
    """
    
    def __init__(self):
        self.templates = SCENARIO_TEMPLATES
        self.active_scenario: Optional[ScenarioConfig] = None
    
    def get_template(self, scenario_type: ScenarioType) -> ScenarioConfig:
        """Get scenario template by type."""
        return self.templates.get(scenario_type, self.templates[ScenarioType.GENERIC])
    
    def apply_scenario(
        self,
        scenario_type: ScenarioType,
        config: Optional[TrustRAGConfig] = None
    ) -> TrustRAGConfig:
        """
        Apply scenario configuration to system config.
        
        Args:
            scenario_type: Type of scenario to apply
            config: Config to modify (if None, uses global config)
            
        Returns:
            Modified config
        """
        if config is None:
            config = get_config()
        
        template = self.get_template(scenario_type)
        self.active_scenario = template
        
        # Apply thresholds
        config.query_thresholds.confidence_threshold = template.min_confidence_threshold
        
        # Apply source authority weights if provided
        if template.source_authority_weights:
            for source_type, weight in template.source_authority_weights.items():
                if hasattr(config.source_authority, source_type):
                    setattr(config.source_authority, source_type, weight)
        
        # Store scenario in custom thresholds
        config.query_thresholds.__dict__.update({
            "scenario_type": template.scenario_type.value,
            "require_multiple_sources": template.require_multiple_sources,
            "min_source_count": template.min_source_count,
            "allow_ocr_for_numeric": template.allow_ocr_for_numeric,
            "require_native_text": template.require_native_text,
            "conflict_resolution": template.conflict_resolution,
            "evidence_quality_requirement": template.evidence_quality_requirement,
            "always_disclose_conflicts": template.always_disclose_conflicts,
            "always_disclose_ocr": template.always_disclose_ocr,
            "always_disclose_degraded": template.always_disclose_degraded
        })
        
        return config
    
    def get_active_scenario(self) -> Optional[ScenarioConfig]:
        """Get currently active scenario."""
        return self.active_scenario
    
    def create_custom_scenario(
        self,
        name: str,
        base_type: ScenarioType = ScenarioType.GENERIC,
        **overrides
    ) -> ScenarioConfig:
        """
        Create custom scenario based on template.
        
        Args:
            name: Scenario name
            base_type: Base template to use
            **overrides: Configuration overrides
            
        Returns:
            Custom scenario config
        """
        base = self.get_template(base_type)
        config_dict = base.model_dump()
        config_dict.update(overrides)
        config_dict["scenario_name"] = name
        return ScenarioConfig(**config_dict)


# Global scenario manager
_scenario_manager: Optional[ScenarioManager] = None


def get_scenario_manager() -> ScenarioManager:
    """Get or create global scenario manager."""
    global _scenario_manager
    if _scenario_manager is None:
        _scenario_manager = ScenarioManager()
    return _scenario_manager



