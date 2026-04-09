# Plan — BATCH-AEX-FIX-02 — 2026-04-09

## Prompt type
PLAN

## Roadmap item
BATCH-AEX-FIX-02

## Objective
Close the fix re-entry repo-write admission bypass by propagating existing lineage into fix requests and enforcing fail-closed mutation intent detection at PQX handoff.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AEX-FIX-02-2026-04-09.md | CREATE | Required written plan for a >2 file BUILD batch. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Forward existing repo-write admission lineage through `_build_fix_request()` for fix re-entry. |
| spectrum_systems/orchestration/pqx_handoff_adapter.py | MODIFY | Make mutation-intent detection fail closed when intent is unknown. |
| tests/test_cycle_runner.py | MODIFY | Add fix re-entry fail-closed/success enforcement tests and unknown-intent handoff test. |
| tests/test_pqx_handoff_adapter.py | MODIFY | Align non-mutating test fixtures with explicit non-mutation declaration after fail-closed hardening. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py`
2. `pytest tests/test_pqx_handoff_adapter.py`
3. `pytest tests/test_aex_repo_write_boundary_structural.py`

## Scope exclusions
- Do not redesign cycle runner state logic.
- Do not add new modules, schemas, or admission systems.
- Do not weaken existing execution_ready/TLC lineage protections.
- Do not redesign structural boundary scan framework.

## Dependencies
- None.
