from trust_rag.engine.retrieval.types import IntentType

class RetrievalIntentAnalyzer:
    def analyze(self, query: str) -> IntentType:
        q = query.lower()
        
        # Numeric / Financial
        if any(k in q for k in ["%", "$", "￥", "ratio", "rate", "growth", "revenue", "profit", "amount", "sum", "total", "增长", "同比", "环比", "金额"]):
            return IntentType.NUMERIC_JUDGMENT
            
        # Comparison
        if any(k in q for k in ["compare", "vs", "versus", "difference", "between", "contrast", "对比", "区别", "差异"]):
            return IntentType.COMPARISON
            
        # Policy / Compliance
        if any(k in q for k in ["policy", "rule", "compliance", "allowed", "prohibited", "legal", "clause", "规定", "条款", "是否允许", "合规"]):
            return IntentType.POLICY_MATCH
            
        # Fact Check (Strong assertions)
        if any(k in q for k in ["verify", "fact", "true", "false", "correct", "claim", "是真的吗", "核实"]):
            return IntentType.FACT_CHECK
            
        return IntentType.OPEN_QUERY
