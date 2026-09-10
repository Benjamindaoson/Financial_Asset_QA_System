"""
GA-Level Parsing Failure Taxonomy.
Classifies and quantifies deep document parsing failures.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ParsingFailureType(Enum):
    """Types of parsing failures."""
    TABLE_AMBIGUITY = "table_ambiguity"
    CROSS_PAGE_MISALIGNMENT = "cross_page_misalignment"
    OCR_LOW_CONFIDENCE = "ocr_low_confidence"
    STRUCTURE_BREAKAGE = "structure_breakage"
    LAYOUT_INCONSISTENCY = "layout_inconsistency"
    SEMANTIC_SKELETON_BREAKAGE = "semantic_skeleton_breakage"


@dataclass
class ParsingFailure:
    """A parsing failure instance."""
    failure_type: ParsingFailureType
    description: str
    severity: str  # "low", "medium", "high"
    affected_elements: Optional[Dict[str, Any]] = None
    confidence_score: float = 0.0


class ParsingFailureTaxonomy:
    """
    GA-Level Parsing Failure Taxonomy.
    Classifies parsing failures and computes their impact on evidence quality.
    """

    def __init__(self):
        self.failure_impacts = {
            ParsingFailureType.TABLE_AMBIGUITY: 0.3,
            ParsingFailureType.CROSS_PAGE_MISALIGNMENT: 0.4,
            ParsingFailureType.OCR_LOW_CONFIDENCE: 0.5,
            ParsingFailureType.STRUCTURE_BREAKAGE: 0.6,
            ParsingFailureType.LAYOUT_INCONSISTENCY: 0.2,
            ParsingFailureType.SEMANTIC_SKELETON_BREAKAGE: 0.7
        }

    def classify_failure(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Optional[ParsingFailure]:
        """
        Classify a parsing error into a failure type.

        Args:
            error_message: The error message
            context: Additional context about the parsing failure

        Returns:
            ParsingFailure instance or None if unclassified
        """
        error_lower = error_message.lower()

        if "table" in error_lower and ("ambiguous" in error_lower or "unclear" in error_lower):
            return ParsingFailure(
                failure_type=ParsingFailureType.TABLE_AMBIGUITY,
                description="Table structure is ambiguous or unclear",
                severity="medium",
                affected_elements=context
            )

        if "cross" in error_lower and "page" in error_lower:
            return ParsingFailure(
                failure_type=ParsingFailureType.CROSS_PAGE_MISALIGNMENT,
                description="Content spans multiple pages with misalignment",
                severity="high",
                affected_elements=context
            )

        if "ocr" in error_lower and ("low" in error_lower or "confidence" in error_lower):
            return ParsingFailure(
                failure_type=ParsingFailureType.OCR_LOW_CONFIDENCE,
                description="OCR text has low confidence score",
                severity="high",
                affected_elements=context
            )

        if "structure" in error_lower and "break" in error_lower:
            return ParsingFailure(
                failure_type=ParsingFailureType.STRUCTURE_BREAKAGE,
                description="Document structure is broken or incomplete",
                severity="high",
                affected_elements=context
            )

        return None

    def get_impact_score(self, failure: ParsingFailure) -> float:
        """
        Get the confidence impact score for a parsing failure.

        Args:
            failure: The parsing failure

        Returns:
            Impact score between 0.0 and 1.0 (higher = more severe impact)
        """
        base_impact = self.failure_impacts.get(failure.failure_type, 0.1)

        # Adjust based on severity
        severity_multiplier = {"low": 0.5, "medium": 1.0, "high": 1.5}
        severity_mult = severity_multiplier.get(failure.severity, 1.0)

        # Adjust based on confidence score if available
        confidence_adjustment = 1.0 - failure.confidence_score

        return min(base_impact * severity_mult * confidence_adjustment, 1.0)