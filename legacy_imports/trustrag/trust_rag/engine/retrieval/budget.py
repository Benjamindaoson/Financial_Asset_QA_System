from trust_rag.engine.retrieval.types import RiskLevel, IntentType, RetrievalBudget

class RetrievalBudgetController:
    def allocate(self, intent: IntentType, risk: RiskLevel) -> RetrievalBudget:
        # Default Baseline
        max_chunks = 10
        min_evidence = 1
        per_index_cap = 5
        
        if risk == RiskLevel.HIGH:
            # High Risk: Precision over Recall. Reduce noise.
            max_chunks = 5
            min_evidence = 2
            per_index_cap = 3
        elif risk == RiskLevel.LOW:
            # Low Risk: Exploration allowed.
            max_chunks = 20
            min_evidence = 1
            per_index_cap = 10
            
        # Intent Tweaks
        if intent == IntentType.COMPARISON:
            # Comparison needs more sources
            max_chunks = max(max_chunks, 8)
            min_evidence = max(min_evidence, 2)
            
        if intent == IntentType.NUMERIC_JUDGMENT:
            # Specificity is key, keep list tight to avoid number soup
            max_chunks = min(max_chunks, 5)

        return RetrievalBudget(
            max_chunks=max_chunks,
            min_evidence_units=min_evidence,
            per_index_cap=per_index_cap
        )
