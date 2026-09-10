# TrustRAG Failure Modes & System Protection

To ensure high-trust operation, TrustRAG explicitly defines its "failures." Some behaviors that might look like errors are actually **System Protection Mechanisms**.

## 1. Design-By-Intent Failures (Safe Refusals)
These occur when the system intentionally refuses to provide an answer to protect the user from hallucinations.

| Failure Code | Name | Cause | User Action |
| :--- | :--- | :--- | :--- |
| **R1** | Out of Scope | Query is non-financial or non-compliance related. | Refine query to focus on document facts. |
| **R2** | Rank-1 Conflict | Two high-authority sources (e.g., 10-K) contradict each other. | Check the `audit_trail` for source discrepancies. |
| **R3** | Low Evidence | Evidence score is below `SufficiencyCritic` threshold. | Ingest better quality or more recent documents. |

## 2. Input-Level Failures (Data Quality)
These occur due to the nature of the provided input documents.

- **OCR Degradation**: If a scan is too blurry, `QualityGate` will mark the ingestion as `DEGRADED`.
- **Structural Ambiguity**: Tables with missing headers or multi-column spanning that cannot be atomic-chunked.
- **Temporal Gap**: Querying for a period (e.g., Q4 2024) before the data has been ingested.

## 3. System Protection Behaviors
The system will "fail fast" in the following ways:

1. **Mandatory Refusal**: Instead of hallucinating a number, the system returns a structured `REFUSE` verdict. This is a **Feature**, not a bug.
2. **FastPath Early Exit**: If a query is ambiguous, the FastPath router will bypass the cache and force a full RAG cycle to ensure precision.
3. **Budget Exhaustion**: If the retrieval budget is too low for the required accuracy, the system will refuse rather than provide a partial answer.

---
**Status**: Release v1.0
**Reference**: See `trust_rag/evaluation/failure_taxonomy.py` for implementation.

