# TrustRAG Engineering Guarantees

Every claim made by TrustRAG is backed by specific code implementations and verified by tests.

## 1. Guarantee: Cognitive Isolation
- **Claim**: The LLM never sees raw data for extraction; it only renders verified bindings.
- **Evidence**: See `trust_rag/system.py` - The `verdict.bindings` are prepared *before* the `renderer.generate_answer` call.
- **Verification**: `tests/integration/test_sealed_pipeline.py` - Ensuring `ALLOW` verdicts only contain data from the `fact_store`.

## 2. Guarantee: Deterministic FastPath
- **Claim**: Factual queries result in identical outputs regardless of LLM state.
- **Evidence**: `trust_rag/core/offline/canonical_fact_store.py` - Exact key matching logic.
- **Verification**: `pytest tests/integration/test_sealed_pipeline.py::test_fast_path_extraction`

## 3. Guarantee: evidence-constrained generation Retrieval
- **Claim**: Numbers not found in tables or verified text chunks are never emitted.
- **Evidence**: `trust_rag/core/judgment/validation.py` (`PostBindingVerifier`) - Cross-checks bindings against retrieval candidates.
- **Verification**: `tests/integration/test_sealed_pipeline.py::test_mandatory_refusal_insufficient_evidence`

## 4. Guarantee: Authority-Based Conflict Resolution
- **Claim**: 10-K filings always override News/Decks if values differ.
- **Evidence**: `trust_rag/core/judgment/orchestrator.py` - Ranking logic during arbitration.
- **Verification**: `tests/unit/test_phase_6_final.py`

---
**Audit Status**: Verified against Release v1.0

