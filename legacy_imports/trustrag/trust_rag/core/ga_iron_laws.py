"""
GA-LEVEL IRON LAWS - NON-REVERSIBLE SYSTEM CONSTRAINTS
"""
import logging
from typing import Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class IronLawViolation(Enum):
    """Critical violations that cannot be tolerated."""
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIED_CITATIONS = "unverified_citations"
    LOW_CONFIDENCE_ANSWER = "low_confidence_answer"
    PARSING_FAILURE_IGNORED = "parsing_failure_ignored"
    INCONSISTENT_MULTIMODAL = "inconsistent_multimodal"
    STRUCTURED_EVIDENCE_MISUSED = "structured_evidence_misused"
    NUMERIC_PRECISION_FAILURE = "numeric_precision_failure"


class GAIronLaws:
    """
    GA-LEVEL IRON LAWS (Hard constraints)
    """
    MIN_EVIDENCE_QUALITY = 0.6
    MIN_ANSWER_CONFIDENCE = 0.5

    @staticmethod
    def enforce_evidence_sufficiency(evidence_list: List[Any], query: str) -> Optional[str]:
        if not evidence_list:
            return "INSUFFICIENT_EVIDENCE: No evidence available for query"
        return None

    @staticmethod
    def enforce_confidence_threshold(confidence_score: float) -> Optional[str]:
        if confidence_score < GAIronLaws.MIN_ANSWER_CONFIDENCE:
            return f"LOW_CONFIDENCE_ANSWER: Confidence {confidence_score:.2f} below minimum {GAIronLaws.MIN_ANSWER_CONFIDENCE}"
        return None

    @staticmethod
    def enforce_citation_verification(citations_verified: Optional[bool]) -> Optional[str]:
        if not citations_verified:
            return "UNVERIFIED_CITATIONS: Answer contains unverifiable citations"
        return None

    @staticmethod
    def enforce_numeric_precision(answer_text: str, evidence_texts: List[str]) -> Optional[str]:
        """GA Iron Law: Numbers in answer must exist in evidence."""
        import re
        # Simple extraction of numbers (integers, decimals, percentages)
        # Exclude years (4 digits starting with 19 or 20 often lead to false positives if not careful, but for now we include)
        # We'll use a slightly looser check: if answer has number x, evidence must have x.
        
        # Regex for numbers: \d+(\.\d+)?%?
        # But we want to avoid matching parts of other numbers.
        # Strict checking is hard. For P1, we check if distinct numbers in answer appear in evidence.
        
        numbers = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', answer_text))
        if not numbers:
            return None
            
        combined_evidence = " ".join(evidence_texts)
        
        missing_numbers = []
        for num in numbers:
            # Check if num exists in evidence
            if num not in combined_evidence:
                # Try to loosen check (e.g. 1000 vs 1,000)
                normalized_num = num.replace(',', '')
                if normalized_num not in combined_evidence.replace(',', ''):
                     missing_numbers.append(num)
        
        if missing_numbers:
             return f"NUMERIC_PRECISION_FAILURE: Numbers {missing_numbers} in answer not found in evidence"
        return None


class IronLawEnforcer:
    """
    Runtime enforcer of GA Iron Laws.
    """

    def __init__(self):
        self.iron_laws = GAIronLaws()

    def enforce_before_generation(self, evidence_list: List[Any], query: str) -> List[str]:
        violations = []
        violation = self.iron_laws.enforce_evidence_sufficiency(evidence_list, query)
        if violation:
            violations.append(violation)
        return violations

    def enforce_after_generation(
        self,
        evidence_list: List[Any],
        answer_text: str,
        confidence_score: float,
        query: str,
        citations_verified: Optional[bool] = None
    ) -> List[str]:
        violations = []
        violation = self.iron_laws.enforce_confidence_threshold(confidence_score)
        if violation:
            violations.append(violation)
        if citation_violation:
            violations.append(citation_violation)
            
        # extract evidence text
        evidence_texts = []
        for ev in evidence_list:
             # Assuming evidence items have 'value' or 'text'
             val = getattr(ev, 'value', '') or getattr(ev, 'text', '')
             if val:
                 evidence_texts.append(str(val))
                 
        numeric_violation = self.iron_laws.enforce_numeric_precision(answer_text, evidence_texts)
        if numeric_violation:
            violations.append(numeric_violation)
            
        return violations
