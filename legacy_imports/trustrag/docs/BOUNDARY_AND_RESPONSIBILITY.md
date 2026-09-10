# TrustRAG System Boundary & Responsibility Statement

## 1. Scope of Guarantee (What We Guarantee)
TrustRAG is designed for **High-Precision Financial Evidence Extraction**. We provide the following deterministic checks:

- **Cognitive Isolation**: The LLM is strictly used as a language renderer. It is mathematically impossible for the LLM to introduce a numeric value not present in the verified evidence bindings.
- **Traceability**: Every numeric output is bidirectionally linked to a source `evidence_id`, `page_number`, and `bbox` (if applicable).
- **Determinism**: For a fixed `fact_store` and query, the system will produce identical logic paths and results (FastPath/DerivativePath).
- **Default Distrust**: Any ambiguity or conflict between sources (e.g., News vs. SEC Filing) will trigger a mandatory refusal (`REFUSE`) rather than a "best guess."

## 2. Out of Scope (What We Do NOT Guarantee)
TrustRAG is **NOT** a general-purpose conversational agent.

- **Generative Reasoning**: We do not perform speculative reasoning (e.g., "What will happen to the stock price?").
- **External Knowledge**: The system ignores its internal pre-trained knowledge in favor of provided documents.
- **Natural Fluency**: We prioritize accuracy over conversational flow. Answers may appear stiff or repetitive.
- **Real-time Data**: Unless explicitly indexed, the system has no awareness of real-time market movements.

## 3. Mandatory Refusal Conditions (REFUSE)
The system will definitively refuse to answer in the following scenarios:
1. **Out of Domain**: Query is not financial/compliance-related (e.g., "Who won the World Cup?").
2. **Conflicting Evidence**: Two Rank-1 sources provide different values for the same metric/period.
3. **Insufficient Confidence**: No table or chart data supports the text-based claims.
4. **Temporal Ambiguity**: The query refers to a period (e.g., "last month") not clearly defined in the available corpus.

## 4. User Responsibilities (Input Integrity)
- **Document Quality**: Garbage in, garbage out. Hand-written notes or blurry scans may degrade OCR quality (tracked via `QualityGate`).
- **Query Clarity**: Ambiguous queries (e.g., "What is the margin?") without specifying the entity or period will be refused.
- **Factual Corrections**: Users must use the provided `audit_trail` to verify Rank-1 sources if a conflict is flagged.

---
**Status**: Release v1.0 (Validated Prototype Core)
**Contact**: TrustRAG Maintainers

