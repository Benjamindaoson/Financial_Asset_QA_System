# Repository Consolidation - 2026-09-10

## Source Repository

- `Benjamindaoson/Financial_Asset_QA_System_master`
- Source HEAD audited: `7f4ecf1`
- Canonical target: `Benjamindaoson/Financial_Asset_QA_System`
- Target HEAD before import: `7f10333`

## Audit Result

The source repository was an older duplicate/predecessor of the canonical
Financial QA project. Hash comparison found 195 files with identical paths and
content. Most source-only files were not product assets:

- 117 files under `.agents/skills/`
- generated artifacts such as `.coverage`, `.pyc`, local DB files, and frontend
  `dist/`
- local `.env`
- placeholder deployment workflow
- historical reports with unsupported improvement and readiness claims

## Migrated Assets

The following unique engineering assets were preserved under
`legacy_imports/financial_asset_qa_system_master/`:

- old multi-domain RAG domain classifier
- offline model snapshot resolver
- old RAG pipeline snapshot
- old multi-domain vector-index builder
- old hybrid-RAG and migration smoke scripts

These files are isolated for reference and are not connected to the active
runtime.

## Excluded Assets

The old upgrade reports were intentionally not migrated because they included
claims such as percentage uplift, `100%` completion, and production-readiness
language without durable benchmark or production evidence. Generated artifacts,
local environment files, and copied third-party/general agent skills were also
excluded.

## Final Decision

`Financial_Asset_QA_System_master` can be deleted after this commit is present
on `Financial_Asset_QA_System/master`, because all useful unique assets have
been preserved in the canonical repository and the remaining source content is
duplicate, generated, local, or unsuitable for public portfolio presentation.
