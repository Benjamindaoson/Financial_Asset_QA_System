from typing import List, Dict, Any
from trust_rag.engine.retrieval.types import RetrievalHit, IntentType, RetrievalBudget

class EvidenceSufficiencyChecker:
    def check(self, hits: List[RetrievalHit], intent: IntentType, budget: RetrievalBudget) -> Dict[str, Any]:
        result = {
            "sufficient": True,
            "reason": "OK",
            "signals": {}
        }
        
        # 0. Basic Check
        if not hits:
            return {
                "sufficient": False,
                "reason": "No hits found",
                "signals": {"hit_count": 0}
            }

        # 1. Numeric Check
        if intent == IntentType.NUMERIC_JUDGMENT:
            # Must have at least one numeric_signature or table hit
            has_numeric = any(h.index_type in ["numeric_signature", "table_row"] for h in hits)
            if not has_numeric:
                # Fallback: maybe dense text has it? Hard to know deteministically without re-parsing.
                # Strict Mode: return insufficient
                return {
                    "sufficient": False,
                    "reason": "Numeric intent requires numeric/table evidence",
                    "signals": {"has_numeric_index_source": False}
                }
                
        # 2. Comparison Check
        if intent == IntentType.COMPARISON:
            # Need at least 2 distinct chunks (implying potentially diff sources or diff sections)
            unique_chunks = {h.chunk_id for h in hits}
            if len(unique_chunks) < 2:
                 return {
                    "sufficient": False,
                    "reason": "Comparison requires at least 2 distinct evidence sources",
                    "signals": {"unique_chunk_count": len(unique_chunks)}
                }

        # 3. Budget Min Check
        # Assuming provenance is populated correctly
        if len(hits) < budget.min_evidence_units:
             return {
                "sufficient": False, # Or Warning? Strict = False
                "reason": f"Hit count {len(hits)} below budget min {budget.min_evidence_units}",
                "signals": {"hit_count": len(hits)}
            }

        return result
