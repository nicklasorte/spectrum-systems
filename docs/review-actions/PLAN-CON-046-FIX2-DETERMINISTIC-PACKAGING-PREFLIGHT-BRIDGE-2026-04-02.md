# Plan — CON-046-FIX2 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-046-FIX2 — Deterministic study_state packaging + preflight authority bridge completion

## Objective
Restore deterministic study_state packaging and complete deterministic preflight authority bridging for commit-range inspection and governed PQX evidence paths without adding new decision logic.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-046-FIX2-DETERMINISTIC-PACKAGING-PREFLIGHT-BRIDGE-2026-04-02.md | CREATE | Required plan artifact for multi-file fix slice |
| PLANS.md | MODIFY | Register active CON-046-FIX2 plan |
| spectrum_systems/modules/study_state.py | MODIFY | Remove runtime-varying study_state timestamp source and use deterministic source-derived timestamp |
| scripts/run_contract_preflight.py | MODIFY | Complete explicit authority-evidence resolution bridge and commit-range gate semantics |
| tests/test_artifact_packaging_and_study_state.py | MODIFY | Add deterministic study_state timestamp packaging regression coverage |
| tests/test_contract_preflight.py | MODIFY | Add/adjust authority bridge and commit-range allow/block semantics coverage |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_artifact_packaging_and_study_state.py`
2. `pytest -q tests/test_contract_preflight.py`
3. `pytest -q tests/test_pqx_sequential_loop.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/run_contract_preflight.py --changed-path ...`
8. `python scripts/run_contract_preflight.py --base-ref ... --head-ref ...`

## Scope exclusions
- Do not add new artifact types.
- Do not alter evaluation or enforcement decision logic.
- Do not add filesystem discovery as primary authority resolution.
- Do not redesign PQX loop architecture.

## Dependencies
- Existing `pqx_slice_execution_record` authority semantics (CON-039) remain authoritative.
- Existing contract preflight artifact and control-signal contracts remain authoritative.
