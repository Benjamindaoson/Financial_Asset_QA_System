"""
Integration of evidence quality signals into routing executor.
"""
from typing import Dict, Any, Optional
from trust_rag.engine.ingest.quality.evidence_signals import (
    TableQualitySignal,
    MetricAlignmentGate,
    AlignmentResult,
    apply_quality_gate
)

class QualityAwareRouter:
    """
    Router that integrates quality signals into decision making.
    """
    
    def __init__(self):
        self.alignment_gate = MetricAlignmentGate()
        self.quality_threshold = 0.85
    
    def pre_judgment_check(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Pre-judgment gate: check if query can proceed or needs clarification.
        
        Args:
            query: User query
            context: Optional context
        
        Returns:
            (can_proceed, refusal_reason)
        """
        # Check metric alignment
        alignment = self.alignment_gate.process(query)
        
        if not alignment.aligned:
            refusal_reason = f"Query requires clarification. {alignment.suggestion}"
            return False, refusal_reason
        
        return True, None
    
    def evaluate_table_quality(
        self,
        table_signal: TableQualitySignal,
        query_requires_precision: bool = True
    ) -> tuple[bool, Optional[str]]:
        """
        Evaluate if table quality is sufficient for query.
        
        Args:
            table_signal: Quality signal for table
            query_requires_precision: Whether query needs high precision
        
        Returns:
            (can_use_table, warning_message)
        """
        if query_requires_precision:
            if not table_signal.is_safe_for_numeric_query(self.quality_threshold):
                warning = table_signal.get_quality_warning()
                return False, f"Table quality insufficient for numeric extraction. {warning}"
        
        # For non-precision queries, allow but warn
        if table_signal.confidence < 0.7:
            warning = table_signal.get_quality_warning()
            return True, warning
        
        return True, None
    
    def route_with_quality_awareness(
        self,
        query: str,
        retrieved_tables: list[TableQualitySignal],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route query with quality awareness.
        
        Returns routing decision with quality considerations.
        """
        # Step 1: Pre-judgment check
        can_proceed, refusal_reason = self.pre_judgment_check(query, context)
        
        if not can_proceed:
            return {
                "decision": "refuse",
                "reason": refusal_reason,
                "degradation_level": 3
            }
        
        # Step 2: Evaluate table quality
        usable_tables = []
        warnings = []
        
        for table in retrieved_tables:
            can_use, warning = self.evaluate_table_quality(table, query_requires_precision=True)
            
            if can_use:
                usable_tables.append(table)
                if warning:
                    warnings.append(warning)
        
        if not usable_tables:
            return {
                "decision": "refuse",
                "reason": "No tables with sufficient quality found for this query.",
                "degradation_level": 2,
                "warnings": warnings
            }
        
        # Step 3: Proceed with best quality table
        best_table = max(usable_tables, key=lambda t: t.confidence)
        
        return {
            "decision": "proceed",
            "selected_table": best_table.table_id,
            "confidence": best_table.confidence,
            "warnings": warnings if warnings else None
        }


# Example integration
if __name__ == "__main__":
    router = QualityAwareRouter()
    
    # Test 1: Ambiguous query
    print("Test 1: Ambiguous query")
    can_proceed, reason = router.pre_judgment_check("What was Nvidia's revenue growth?")
    print(f"  Can proceed: {can_proceed}")
    print(f"  Reason: {reason}")
    print()
    
    # Test 2: Clear query
    print("Test 2: Clear query")
    can_proceed, reason = router.pre_judgment_check("What was Nvidia's YoY revenue growth in FY2024?")
    print(f"  Can proceed: {can_proceed}")
    print()
    
    # Test 3: Low quality table
    print("Test 3: Low quality table")
    low_quality_table = TableQualitySignal(
        table_id="table_001",
        header_similarity=0.65,
        column_alignment_score=0.70,
        row_count=5,
        column_count=3,
        sum_check_passed=False,
        unit_consistency=False,
        has_missing_cells=True,
        spans_multiple_pages=True
    )
    
    decision = router.route_with_quality_awareness(
        "What was Nvidia's YoY revenue growth in FY2024?",
        [low_quality_table]
    )
    print(f"  Decision: {decision}")
    print()
    
    # Test 4: High quality table
    print("Test 4: High quality table")
    high_quality_table = TableQualitySignal(
        table_id="table_002",
        header_similarity=0.95,
        column_alignment_score=0.92,
        row_count=10,
        column_count=4,
        sum_check_passed=True,
        unit_consistency=True,
        has_missing_cells=False,
        spans_multiple_pages=False
    )
    
    decision = router.route_with_quality_awareness(
        "What was Nvidia's YoY revenue growth in FY2024?",
        [high_quality_table]
    )
    print(f"  Decision: {decision}")
