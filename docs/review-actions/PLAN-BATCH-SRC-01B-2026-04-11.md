# Plan — BATCH-SRC-01B — 2026-04-11

## Prompt type
BUILD

## Roadmap item
BATCH-SRC-01B

## Objective
Repair source-authority ingestion compatibility by restoring expected structured-source schema shape, refreshing source-authority digests, and updating stale source-count test assumptions without weakening fail-closed governance.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SRC-01B-2026-04-11.md | CREATE | Required execution plan for multi-file repair. |
| scripts/sync_project_design_sources.py | MODIFY | Emit compatibility-shaped structured records + digest refresh helper behavior. |
| config/policy/tpa_scope_policy.json | MODIFY | Refresh source-authority digest values after index updates. |
| docs/source_structured/project_design_*.json | MODIFY | Align records to expected `source_document`/traceability shape. |
| docs/source_indexes/source_inventory.json | MODIFY | Refresh deterministic inventory after compatibility regeneration. |
| docs/source_indexes/component_source_map.json | MODIFY | Refresh deterministic component map after compatibility regeneration. |
| docs/source_indexes/obligation_index.json | MODIFY | Refresh deterministic obligation index after compatibility regeneration. |
| tests/test_source_structured_files_validate.py | MODIFY | Remove stale fixed-count assumption and validate expanded corpus shape. |
| tests/test_source_indexes_build.py | MODIFY | Remove stale six-source assumption and assert inclusion semantics. |
| tests/test_sync_project_design_sources.py | MODIFY | Validate compatibility shape fields for newly generated structured sources. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_source_structured_files_validate.py`
2. `pytest tests/test_source_indexes_build.py`
3. `pytest tests/test_tpa_scope_policy.py`
4. `pytest tests/test_prompt_queue_sequence_cli.py`
5. `pytest tests/test_roadmap_execution_cli.py`
6. `pytest tests/test_roadmap_draft_approver.py`
7. `pytest tests/test_pqx_slice_runner.py`
8. `pytest tests/test_sync_project_design_sources.py`

## Scope exclusions
- Do not remove ingested source corpus.
- Do not bypass digest checks or fail-closed controls.
- Do not implement roadmap compiler or execution automation.

## Dependencies
- BATCH-SRC-01A changes are present.
