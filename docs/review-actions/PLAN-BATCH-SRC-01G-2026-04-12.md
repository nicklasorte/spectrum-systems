# Plan — BATCH-SRC-01G — 2026-04-12

## Prompt type
BUILD

## Roadmap item
BATCH-SRC-01G

## Objective
Prevent mutation of canonical source-authority index files during tests/runtime by enforcing explicit write overrides and keeping tests on isolated temp paths.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SRC-01G-2026-04-12.md | CREATE | Required multi-file plan artifact. |
| scripts/build_source_indexes.py | MODIFY | Add canonical index write guard requiring explicit override. |
| scripts/sync_project_design_sources.py | MODIFY | Add canonical index write guard requiring explicit override. |
| tests/test_source_indexes_build.py | MODIFY | Add regression asserting canonical write is blocked without override. |
| tests/test_sync_project_design_sources.py | MODIFY | Add regression asserting canonical write is blocked without override. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_source_indexes_build.py -q`
2. `pytest tests/test_sync_project_design_sources.py -q`
3. `pytest tests/test_tpa_scope_policy.py -q`
4. `pytest tests/test_tpa_sequence_runner.py -q`
5. `pytest tests/test_top_level_conductor.py -q`
6. `pytest tests/test_system_end_to_end_governed_loop.py -q`
7. `pytest tests/test_tlc_requires_admission_for_repo_write.py -q`
8. `pytest tests/test_system_handoff_integrity.py -q`
9. `pytest`

## Scope exclusions
- Do not weaken digest validation.
- Do not recompute policy digests dynamically in runtime paths.
- Do not alter unrelated runtime subsystems.

## Dependencies
- BATCH-SRC-01A through 01F already merged on branch.
