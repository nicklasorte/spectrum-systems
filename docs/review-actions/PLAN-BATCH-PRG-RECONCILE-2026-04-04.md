# Plan — BATCH-PRG-RECONCILE — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-PRG-RECONCILE

## Objective
Reconcile PRG-ENFORCE fail-closed alignment with MVP-20 drill fixtures so drill semantics are explicit and deterministic under stricter governance.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PRG-RECONCILE-2026-04-04.md | CREATE | Required plan-first artifact for reconciliation batch. |
| PLANS.md | MODIFY | Register reconciliation plan in active plans. |
| spectrum_systems/modules/runtime/mvp_20_slice_execution.py | MODIFY | Fix drill/program signal mismatch and clarify report semantics. |
| tests/test_system_mvp_validation.py | MODIFY | Encode intended drill semantics and assertions under PRG-ENFORCE. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_system_mvp_validation.py`
2. `pytest tests/test_program_layer.py`
3. `pytest tests/test_roadmap_multi_batch_executor.py`
4. `pytest tests/test_roadmap_selector.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`
8. `PLAN_FILES="..." .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not weaken fail-closed program enforcement.
- Do not redesign PQX orchestration flow.
- Do not alter non-reconciliation modules.

## Dependencies
- BATCH-PRG-ENFORCE implementation must remain active and authoritative.
