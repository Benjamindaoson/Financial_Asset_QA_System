"""
Answer Contribution Analysis (Phase 6.5).
Establishes causal links between evidence and answers.
"""
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from trust_rag.engine.retrieval.scored_chunk import ScoredChunk
from .selector import SelectedEvidenceSet, EvidenceRole, RiskFlags

class RemovalEffect(str, Enum):
    NO_CHANGE = "no_change"
    ANSWER_CHANGED = "answer_changed"     # Numeric/Logic change
    ANSWER_DEGRADED = "answer_degraded"   # Refusal/Disclosure
    ANSWER_INVALID = "answer_invalid"     # Risk policy violation

class DecisionMode(str, Enum):
    NORMAL = "normal"
    CONSERVATIVE = "conservative"
    REGULATOR = "regulator"

@dataclass
class AnswerContribution:
    """Audit of how evidence contributes to the answer."""
    depends_on: List[str] = field(default_factory=list)      # All affecting evidence
    irrelevant_to_answer: List[str] = field(default_factory=list)
    critical_evidence: List[str] = field(default_factory=list) # Removal causes changed/degraded
    removal_effects: Dict[str, RemovalEffect] = field(default_factory=dict)
    
    # Audit Trace
    analysis_version: str = "6.5"
    analysis_mode: str = "rule_based"
    evidence_checked: int = 0

class AnswerContributionAnalyzer:
    """
    Analyzes causal impact of evidence on final answer.
    Implements Leave-One-Out (LOO) analysis without LLM by default.
    """
    
    def __init__(self, mode: DecisionMode = DecisionMode.NORMAL):
        self.mode = mode

    def analyze(
        self,
        query: str,
        selected_evidence: SelectedEvidenceSet,
        original_answer: Dict[str, Any],
        answer_generator_fn  # Functional dependency for answer generation
    ) -> AnswerContribution:
        """
        Perform Leave-One-Out analysis on core and supporting evidence.
        """
        contribution = AnswerContribution()
        core_ids = [c.evidence_id for c in selected_evidence.core_evidence]
        supp_ids = [c.evidence_id for c in selected_evidence.supporting_evidence]
        candidates_to_test = core_ids + supp_ids
        
        contribution.evidence_checked = len(candidates_to_test)
        
        for ev_id in candidates_to_test:
            # 1. Temporarily remove evidence
            reduced_evidence = self._get_reduced_evidence(selected_evidence, ev_id)
            
            # 2. Re-generate answer (or simulate)
            new_answer = answer_generator_fn(query, reduced_evidence)
            
            # 3. Compare answers
            effect = self._classify_removal_effect(original_answer, new_answer, ev_id, selected_evidence)
            contribution.removal_effects[ev_id] = effect
            
            # 4. Determine dependency
            if effect != RemovalEffect.NO_CHANGE:
                contribution.depends_on.append(ev_id)
                if effect in [RemovalEffect.ANSWER_CHANGED, RemovalEffect.ANSWER_DEGRADED, RemovalEffect.ANSWER_INVALID]:
                    contribution.critical_evidence.append(ev_id)
            else:
                # If removal has no effect and it's not core, it's irrelevant
                if ev_id not in core_ids:
                     contribution.irrelevant_to_answer.append(ev_id)

        # Post-process based on DecisionMode
        self._apply_policy_overrides(contribution, selected_evidence)
        
        return contribution

    def _get_reduced_evidence(
        self, 
        original: SelectedEvidenceSet, 
        exclude_id: str
    ) -> SelectedEvidenceSet:
        """Create a copy of evidence set excluding one evidence ID."""
        return SelectedEvidenceSet(
            core_evidence=[c for c in original.core_evidence if c.evidence_id != exclude_id],
            supporting_evidence=[c for c in original.supporting_evidence if c.evidence_id != exclude_id],
            excluded_evidence=original.excluded_evidence + [c for c in original.core_evidence + original.supporting_evidence if c.evidence_id == exclude_id],
            selection_reason=original.selection_reason.copy(),
            risk_flags=original.risk_flags, # Keep original flags as base
            collapsed_tables=original.collapsed_tables.copy()
        )

    def _classify_removal_effect(
        self,
        old_ans: Dict[str, Any],
        new_ans: Dict[str, Any],
        ev_id: str,
        original_set: SelectedEvidenceSet
    ) -> RemovalEffect:
        """Deterministic comparison of answers."""
        old_text = old_ans.get("text", "").strip()
        new_text = new_ans.get("text", "").strip()
        
        # 1. Refusal/Disclosure check (Degradation)
        old_refusal = old_ans.get("refusal", False)
        new_refusal = new_ans.get("refusal", False)
        
        if not old_refusal and new_refusal:
            return RemovalEffect.ANSWER_DEGRADED
            
        # 2. Structural/Numeric change
        old_numeric = old_ans.get("numeric_value")
        new_numeric = new_ans.get("numeric_value")
        if old_numeric is not None and old_numeric != new_numeric:
            return RemovalEffect.ANSWER_CHANGED
            
        # 3. Semantic comparison (simplified for rule-based)
        if old_text != new_text:
            # If text changes significantly (not just whitespace)
            return RemovalEffect.ANSWER_CHANGED if len(new_text) > 0 else RemovalEffect.ANSWER_DEGRADED

        # 4. Risk rule violation (Invalid)
        # e.g. If specific evidence was the only "native" and now we only have OCR
        if self._violates_risk_policy(new_ans, ev_id, original_set):
            return RemovalEffect.ANSWER_INVALID

        return RemovalEffect.NO_CHANGE

    def _violates_risk_policy(self, ans: Dict[str, Any], removed_id: str, original_set: SelectedEvidenceSet) -> bool:
        """Check if remaining evidence violates bank-grade policies."""
        # Regulator mode is strict
        if self.mode == DecisionMode.REGULATOR:
            # If answer remains but loses its 'native' support
            remaining = [c for c in original_set.core_evidence if c.evidence_id != removed_id]
            has_native = any(c.metadata.get("modality") in ["text_native", "table_native"] for c in remaining)
            if not has_native and ans.get("numeric_value") is not None:
                return True
        return False

    def _apply_policy_overrides(self, contrib: AnswerContribution, selected: SelectedEvidenceSet):
        """Link analysis results back to RiskFlags and apply mode policies."""
        # 1. Critical Evidence linkage
        if not contrib.critical_evidence:
            selected.risk_flags.evidence_insufficient = True
            
        # 2. OCR Critical check
        ocr_critical = []
        for ev_id in contrib.critical_evidence:
            chunk = next((c for c in selected.core_evidence + selected.supporting_evidence if c.evidence_id == ev_id), None)
            if chunk and chunk.metadata.get("modality") in ["text_ocr", "table_ocr"]:
                ocr_critical.append(ev_id)
        
        if ocr_critical:
            selected.risk_flags.requires_human_review = True
            
        # 3. Conservative Mode adjustments
        if self.mode in [DecisionMode.CONSERVATIVE, DecisionMode.REGULATOR]:
            # Any 'answer_changed' in core is automatically critical even if minor strings
             pass # Already handled by logic, but can be scaled
