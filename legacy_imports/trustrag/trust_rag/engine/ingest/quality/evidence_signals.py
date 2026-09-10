"""
Evidence Quality Signals for TrustRAG.
Implements table quality scoring and metric alignment enforcement.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

@dataclass
class TableQualitySignal:
    """
    Quality signal for reconstructed tables (especially cross-page).
    Used to determine if table data is reliable enough for numeric queries.
    """
    table_id: str
    
    # Structural quality
    header_similarity: float  # 0-1, cross-page header match
    column_alignment_score: float  # 0-1, structural consistency
    row_count: int
    column_count: int
    
    # Data validation
    sum_check_passed: bool  # If "Total" row exists, does it match sum?
    unit_consistency: bool  # All cells in column have same unit
    has_missing_cells: bool  # Any N/A, -, or empty cells
    
    # Metadata
    spans_multiple_pages: bool
    page_range: Optional[tuple] = None  # (start_page, end_page)
    
    # Composite score
    confidence: float = 0.0  # 0-1, overall confidence
    
    def __post_init__(self):
        """Calculate composite confidence score."""
        if self.confidence == 0.0:  # Not manually set
            self.confidence = self._calculate_confidence()
    
    def _calculate_confidence(self) -> float:
        """
        Calculate composite confidence score.
        
        Weights:
        - Header similarity: 30%
        - Column alignment: 25%
        - Sum check: 20%
        - Unit consistency: 15%
        - No missing cells: 10%
        """
        score = 0.0
        
        # Header similarity (critical for cross-page tables)
        score += self.header_similarity * 0.30
        
        # Column alignment
        score += self.column_alignment_score * 0.25
        
        # Sum check (if applicable)
        if self.sum_check_passed:
            score += 0.20
        
        # Unit consistency
        if self.unit_consistency:
            score += 0.15
        
        # No missing cells
        if not self.has_missing_cells:
            score += 0.10
        
        return min(score, 1.0)
    
    def is_safe_for_numeric_query(self, threshold: float = 0.85) -> bool:
        """
        Determine if table quality is sufficient for numeric queries.
        
        Args:
            threshold: Minimum confidence required (default 0.85)
        
        Returns:
            True if table is reliable enough for numeric extraction
        """
        return (
            self.confidence >= threshold and
            self.sum_check_passed and
            self.unit_consistency
        )
    
    def get_quality_warning(self) -> Optional[str]:
        """
        Generate warning message if quality is low.
        
        Returns:
            Warning message or None if quality is acceptable
        """
        if self.confidence >= 0.85:
            return None
        
        issues = []
        
        if self.header_similarity < 0.8:
            issues.append("cross-page header mismatch")
        
        if self.column_alignment_score < 0.8:
            issues.append("column alignment issues")
        
        if not self.sum_check_passed:
            issues.append("sum validation failed")
        
        if not self.unit_consistency:
            issues.append("inconsistent units")
        
        if self.has_missing_cells:
            issues.append("missing data cells")
        
        if issues:
            return f"Table quality warning: {', '.join(issues)}. Confidence: {self.confidence:.2f}"
        
        return f"Table quality below threshold. Confidence: {self.confidence:.2f}"


class ComparisonType(str, Enum):
    """Types of time-based comparisons."""
    YOY = "YoY"  # Year-over-Year
    QOQ = "QoQ"  # Quarter-over-Quarter
    MOM = "MoM"  # Month-over-Month
    SEQUENTIAL = "sequential"  # Same as QoQ
    NONE = "none"  # No comparison


class AccountingStandard(str, Enum):
    """Accounting standards."""
    GAAP = "GAAP"
    NON_GAAP = "non-GAAP"
    IFRS = "IFRS"
    ADJUSTED = "adjusted"
    REPORTED = "reported"
    UNKNOWN = "unknown"


@dataclass
class AlignmentResult:
    """Result of metric alignment check."""
    aligned: bool
    missing_dimensions: List[str]  # e.g., ["time_comparison", "accounting_standard"]
    detected_comparison: Optional[ComparisonType] = None
    detected_standard: Optional[AccountingStandard] = None
    suggestion: Optional[str] = None  # What user should specify


class MetricAlignmentGate:
    """
    Pre-judgment gate to enforce metric disambiguation.
    Prevents ambiguous queries from proceeding without clarification.
    """
    
    # Keywords for comparison type detection
    COMPARISON_KEYWORDS = {
        ComparisonType.YOY: ["yoy", "year-over-year", "year over year", "annual growth", "vs last year"],
        ComparisonType.QOQ: ["qoq", "quarter-over-quarter", "quarter over quarter", "vs last quarter"],
        ComparisonType.MOM: ["mom", "month-over-month", "month over month", "vs last month"],
        ComparisonType.SEQUENTIAL: ["sequential", "sequentially"]
    }
    
    # Keywords for accounting standard detection
    STANDARD_KEYWORDS = {
        AccountingStandard.GAAP: ["gaap"],
        AccountingStandard.NON_GAAP: ["non-gaap", "non gaap", "adjusted"],
        AccountingStandard.IFRS: ["ifrs"],
        AccountingStandard.REPORTED: ["reported", "as reported"],
        AccountingStandard.ADJUSTED: ["adjusted"]
    }
    
    # Metrics that require comparison type
    COMPARISON_METRICS = ["growth", "increase", "decrease", "change", "improvement", "decline"]
    
    # Metrics that often have GAAP vs non-GAAP variants
    STANDARD_SENSITIVE_METRICS = [
        "eps", "earnings per share",
        "operating income", "operating margin",
        "net income", "net margin",
        "gross margin", "gross profit"
    ]
    
    def process(self, query: str) -> AlignmentResult:
        """
        Check if query has sufficient metric alignment.
        
        Args:
            query: User query text
        
        Returns:
            AlignmentResult indicating if query is aligned or needs clarification
        """
        query_lower = query.lower()
        missing = []
        
        # Detect comparison type
        detected_comparison = self._detect_comparison_type(query_lower)
        
        # Detect accounting standard
        detected_standard = self._detect_accounting_standard(query_lower)
        
        # Check if comparison is needed but missing
        if self._requires_comparison(query_lower) and detected_comparison == ComparisonType.NONE:
            missing.append("time_comparison")
        
        # Check if accounting standard is needed but missing
        if self._requires_standard(query_lower) and detected_standard == AccountingStandard.UNKNOWN:
            missing.append("accounting_standard")
        
        # Check if period is specified
        if not self._has_period(query_lower):
            missing.append("period")
        
        # Generate suggestion
        suggestion = self._generate_suggestion(missing, query_lower)
        
        return AlignmentResult(
            aligned=len(missing) == 0,
            missing_dimensions=missing,
            detected_comparison=detected_comparison if detected_comparison != ComparisonType.NONE else None,
            detected_standard=detected_standard if detected_standard != AccountingStandard.UNKNOWN else None,
            suggestion=suggestion
        )
    
    def _detect_comparison_type(self, query: str) -> ComparisonType:
        """Detect comparison type from query text."""
        for comp_type, keywords in self.COMPARISON_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return comp_type
        return ComparisonType.NONE
    
    def _detect_accounting_standard(self, query: str) -> AccountingStandard:
        """Detect accounting standard from query text."""
        for standard, keywords in self.STANDARD_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return standard
        return AccountingStandard.UNKNOWN
    
    def _requires_comparison(self, query: str) -> bool:
        """Check if query requires comparison type specification."""
        return any(metric in query for metric in self.COMPARISON_METRICS)
    
    def _requires_standard(self, query: str) -> bool:
        """Check if query requires accounting standard specification."""
        return any(metric in query for metric in self.STANDARD_SENSITIVE_METRICS)
    
    def _has_period(self, query: str) -> bool:
        """Check if query specifies a period."""
        period_patterns = [
            "fy20", "fy 20", "fiscal year",
            "q1", "q2", "q3", "q4",
            "2020", "2021", "2022", "2023", "2024", "2025"
        ]
        return any(pattern in query for pattern in period_patterns)
    
    def _generate_suggestion(self, missing: List[str], query: str) -> Optional[str]:
        """Generate clarification suggestion based on missing dimensions."""
        if not missing:
            return None
        
        suggestions = []
        
        if "time_comparison" in missing:
            suggestions.append("Time comparison (YoY/QoQ/MoM)")
        
        if "accounting_standard" in missing:
            # Determine which standard is likely needed
            if "eps" in query or "earnings" in query:
                suggestions.append("Accounting standard (GAAP or non-GAAP)")
            else:
                suggestions.append("Accounting standard (GAAP/non-GAAP)")
        
        if "period" in missing:
            suggestions.append("Period (e.g., FY2024, Q3 2024)")
        
        return f"Please specify: {', '.join(suggestions)}"


def apply_quality_gate(
    table_signal: TableQualitySignal,
    query_type: str
) -> tuple[bool, Optional[str]]:
    """
    Apply quality gate to determine if query can proceed.
    
    Args:
        table_signal: Quality signal for the table
        query_type: Type of query ("numeric", "comparison", etc.)
    
    Returns:
        (can_proceed, warning_message)
    """
    if query_type == "numeric":
        if not table_signal.is_safe_for_numeric_query():
            warning = table_signal.get_quality_warning()
            return False, f"Cannot extract numeric value: {warning}"
    
    # For other query types, allow but warn
    if table_signal.confidence < 0.7:
        warning = table_signal.get_quality_warning()
        return True, warning
    
    return True, None


# Example usage
if __name__ == "__main__":
    # Example 1: High-quality table
    good_table = TableQualitySignal(
        table_id="revenue_table_001",
        header_similarity=0.95,
        column_alignment_score=0.92,
        row_count=10,
        column_count=4,
        sum_check_passed=True,
        unit_consistency=True,
        has_missing_cells=False,
        spans_multiple_pages=True,
        page_range=(45, 46)
    )
    print(f"Good table confidence: {good_table.confidence:.2f}")
    print(f"Safe for numeric: {good_table.is_safe_for_numeric_query()}")
    print()
    
    # Example 2: Low-quality table
    bad_table = TableQualitySignal(
        table_id="revenue_table_002",
        header_similarity=0.65,
        column_alignment_score=0.70,
        row_count=8,
        column_count=4,
        sum_check_passed=False,
        unit_consistency=False,
        has_missing_cells=True,
        spans_multiple_pages=True,
        page_range=(47, 48)
    )
    print(f"Bad table confidence: {bad_table.confidence:.2f}")
    print(f"Safe for numeric: {bad_table.is_safe_for_numeric_query()}")
    print(f"Warning: {bad_table.get_quality_warning()}")
    print()
    
    # Example 3: Metric alignment
    gate = MetricAlignmentGate()
    
    queries = [
        "What was Nvidia's revenue growth?",  # Ambiguous
        "What was Nvidia's YoY revenue growth in FY2024?",  # Clear
        "What was Nvidia's EPS in FY2024?",  # Missing GAAP/non-GAAP
        "What was Nvidia's non-GAAP EPS in FY2024?",  # Clear
    ]
    
    for query in queries:
        result = gate.process(query)
        print(f"Query: {query}")
        print(f"  Aligned: {result.aligned}")
        if not result.aligned:
            print(f"  Missing: {result.missing_dimensions}")
            print(f"  Suggestion: {result.suggestion}")
        print()
