# Financial Asset QA System — Consolidated

This repository is no longer an active standalone portfolio project.

Its reusable financial RAG capabilities have been consolidated into the
canonical **FinEvidence** project:

**Benjamindaoson/finevidence-financial-rag**

The consolidation keeps the evidence-centric FinEvidence architecture and
incorporates the reusable parts of this repository, including:

- structure-aware and table-aware chunking;
- BM25 lexical retrieval;
- reciprocal-rank fusion;
- Cross-Encoder reranking patterns;
- financial validation ideas relevant to evidence-grounded QA.

Product-specific capabilities were intentionally not carried forward, including
stock dashboards, technical indicators such as RSI/MACD, market-data product
flows, and investment-oriented UI logic.

## Status

**Historical / superseded repository.**

No new feature development should be added here. New financial RAG work,
benchmarks, evaluation, and documentation should go to FinEvidence.

The existing Git history remains available for provenance and reference.
