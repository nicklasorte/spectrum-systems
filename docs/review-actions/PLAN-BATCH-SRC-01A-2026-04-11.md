# Plan — BATCH-SRC-01A — 2026-04-11

## Prompt type
BUILD

## Roadmap item
BATCH-SRC-01A

## Objective
Ingest project-design markdown/PDF sources from `spectrum-data-lake` into deterministic local raw, structured, and indexed authority surfaces with fail-closed completeness validation.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| scripts/sync_project_design_sources.py | CREATE | Implement discovery, sync, structuring, index update, and completeness validation. |
| docs/architecture/source_authority_sync.md | CREATE | Document upstream truth and downstream ingestion model. |
| docs/source_raw/project_design/* | CREATE/MODIFY | Store synchronized raw project-design markdown/PDF/manifests with provenance. |
| docs/source_structured/project_design_*.json | CREATE | Structured per-source authority artifacts for ingested sources. |
| docs/source_indexes/source_inventory.json | MODIFY | Add ingested source inventory and completeness records. |
| docs/source_indexes/component_source_map.json | MODIFY | Map ingested sources into required domain buckets. |
| docs/source_indexes/obligation_index.json | MODIFY | Add conservative obligation entries tied to sources. |
| tests/test_sync_project_design_sources.py | CREATE | Focused tests for discovery, grouping, indexing, validation, and idempotency. |
| docs/review-actions/PLAN-BATCH-SRC-01A-2026-04-11.md | CREATE | Required multi-file execution plan artifact. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_sync_project_design_sources.py`
2. `python scripts/sync_project_design_sources.py --upstream-repo https://github.com/nicklasorte/spectrum-data-lake --validate-only`

## Scope exclusions
- Do not build roadmap compilers or execution automation.
- Do not create a second control plane, policy engine, or certification path.
- Do not refactor unrelated modules.

## Dependencies
- None.
