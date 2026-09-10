"""
Evidence module init.
"""
from .classifier import (
    EvidenceRole, EvidenceRoleClassifier, EvidenceReranker,
    SOURCE_AUTHORITY, MODALITY_TRUST
)
from .selector import (
    EvidenceSelector, SelectedEvidenceSet, SelectionConfig, RiskFlags
)
from .contribution import (
    AnswerContributionAnalyzer, AnswerContribution, RemovalEffect, DecisionMode
)

__all__ = [
    'EvidenceRole', 'EvidenceRoleClassifier', 'EvidenceReranker',
    'SOURCE_AUTHORITY', 'MODALITY_TRUST',
    'EvidenceSelector', 'SelectedEvidenceSet', 'SelectionConfig', 'RiskFlags',
    'AnswerContributionAnalyzer', 'AnswerContribution', 'RemovalEffect', 'DecisionMode',
]
