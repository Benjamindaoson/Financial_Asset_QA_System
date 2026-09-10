# Financial_Asset_QA_System_master Legacy Import

This directory preserves the only useful engineering assets found in the retired
`Financial_Asset_QA_System_master` repository during the 2026-09-10 portfolio
consolidation.

The files here are historical reference material. They are not imported by the
production runtime and should not be treated as the active Financial QA
implementation.

## Preserved Assets

- `backend/app/rag/domain_classifier.py`: heuristic document/domain classifier
  used by the old multi-domain RAG indexing flow.
- `backend/app/rag/model_resolver.py`: offline Hugging Face snapshot resolver
  for local model loading.
- `backend/app/rag/pipeline.py`: old RAG pipeline snapshot that used the domain
  classifier and offline model resolver.
- `backend/scripts/build_vector_index.py`: old multi-domain Chroma index builder
  that split `financial_knowledge` into per-domain collections.
- `backend/scripts/legacy_tests/`: old smoke/e2e scripts for hybrid RAG and RAG
  migration checks.

## Excluded From Migration

- `.agents/skills/`: bundled third-party/general agent skills, not project
  product code.
- `.env`, `.coverage`, `__pycache__`, `.pyc`, local DB files, and frontend
  `dist/`: generated or local-machine artifacts.
- `.github/workflows/deploy.yml`: placeholder deployment workflow with no real
  production target.
- Old upgrade/comparison reports: contained unsupported claims such as
  percentage improvements, `100%` completion, and production-readiness language
  without durable evidence.
- Experimental RAG modules that already exist in the canonical repository under
  `backend/app/rag/`; their differences were limited to import-path rewrites.

## Deletion Decision

`Financial_Asset_QA_System` remains the canonical public repository. After the
files above were preserved here, `Financial_Asset_QA_System_master` had no
remaining unique assets worth keeping as a separate repository.
