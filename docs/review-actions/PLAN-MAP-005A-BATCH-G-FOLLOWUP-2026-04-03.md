# Plan — MAP-005A — 2026-04-03

## Prompt type
PLAN

## Roadmap item
MAP-005A — BATCH-G Follow-Up: Fixture-Mode Certification Boundary Fix

## Objective
Restore deterministic explicit fixture decision outcomes in `run_pqx_slice` without weakening strict MAP-005 certification semantics for explicitly governed readiness paths.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-MAP-005A-BATCH-G-FOLLOWUP-2026-04-03.md | CREATE | Required plan-first artifact for multi-file follow-up fix |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Fence fixture-mode certification acceptance and add explicit strict readiness opt-in boundary |
| tests/test_pqx_slice_runner.py | MODIFY | Regressions + explicit strict-opt-in fixture boundary behavior coverage |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_pqx_slice_runner.py`
2. `pytest tests/test_done_certification.py`
3. `pytest tests/test_evaluation_enforcement_bridge.py`
4. `pytest tests/test_pqx_sequence_runner.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`

## Scope exclusions
- Do not revert MAP-005 certification model changes.
- Do not alter done-certification schema/contract for this fix.
- Do not introduce new orchestration paths.

## Dependencies
- Existing MAP-005 done certification and promotion gate semantics remain authoritative for governed readiness mode.
