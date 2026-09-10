# TrustRAG Canonical Fact Store

The Canonical Fact Store is a read-optimized, deterministic source of truth used for **Fast-Path Routing**. It allows the system to bypass the expensive RAG pipeline (retrieval, reasoning, LLM) for factual queries that have exact matches in our validated data.

## Storage Format
- **Format**: JSONL (Line-delimited JSON).
- **Structure**:
  - Line 1: Metadata (Versions, Count, Timestamp).
  - Lines 2+: `CanonicalFact` objects.

## Canonical Fact Schema
- `entity`: Name of the company/entity.
- `metric`: Financial metric (e.g., revenue, net_income).
- `period`: Time period (e.g., FY2023, Q4_2024).
- `value`: Numeric value.
- `unit`: Currency or unit (e.g., USD, EUR).
- `source_evidence_ids`: List of IDs pointing to the validated filings.
- `source_rank`: Trust level (1=Filing, 2=Deck, 3=News).
- `version_hash`: SHA256 integrity hash.

## Rebuild Conditions
The store **MUST** be rebuilt if any of the following change:
1. `VALIDATION_RULES_VERSION`: Updated strictness in chart/table parsing.
2. `CANONICAL_RESOLUTION_VERSION`: Change in how we pick winners between conflicting documents.
3. **Data Refresh**: New filings ingested.

Version mismatches during online execution will trigger a fallback to the full RAG pipeline to ensure maximum accuracy.

## CLI Usage (Internal)
To rebuild the store from validated evidence:
```bash
python -m trust_rag.core.offline.canonical_fact_builder --input artifacts/validated_facts.json --output artifacts/facts/canonical_store.jsonl
```

## Safety Invariants
- **No Ambiguity**: Facts are only emitted if a clear, non-conflicting winner exists.
- **No Implicit Conversion**: Units must match the query intent exactly.
- **Audit Ready**: Every fast-path response includes the `source_evidence_ids` for human verification.
