# TrustRAG Legacy Import

This directory preserves useful assets from the retired `trustrag` repository
inside the canonical public financial QA repository.

Preserved:

- `trust_rag/` ingestion, retrieval, evidence binding, evaluation, runtime, and
  UI source code.
- `tools/`, `scripts/`, `tests/`, and `requirements/` support assets.
- `docs/` architecture, evaluation, failure-mode, and implementation notes.
- Root-level deployment and upgrade notes that may help future reuse.
- A small number of source files that were already syntactically invalid in the
  predecessor snapshot were renamed to `.py.txt` and retained only as reference
  material.

Excluded:

- Root README marketing copy.
- Generated artifacts, large verification JSON files, cached BM25 indexes,
  `.next` build output, dependency directories, local IDE files, and caches.

Public-portfolio note: the imported text was neutralized where it made
unsupported claims such as absolute hallucination prevention or production
readiness. This import is not part of the active runtime until explicitly
reviewed and promoted.
