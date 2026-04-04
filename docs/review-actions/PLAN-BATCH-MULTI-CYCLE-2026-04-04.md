# Plan — BATCH-MULTI-CYCLE — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-MULTI-CYCLE

## Objective
Prove bounded deterministic multi-cycle governed roadmap execution with explicit stop controls, progress integrity checks, and a governed multi-cycle report artifact.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-MULTI-CYCLE-2026-04-04.md | CREATE | Required PLAN-first artifact for this multi-file BUILD scope. |
| PLANS.md | MODIFY | Register this plan in the active plans table. |
| contracts/schemas/multi_cycle_execution_report.schema.json | CREATE | Define strict contract for governed multi-cycle proof output. |
| contracts/examples/multi_cycle_execution_report.json | CREATE | Golden-path example for the new report contract. |
| contracts/standards-manifest.json | MODIFY | Publish the new contract in canonical manifest pins. |
| spectrum_systems/modules/runtime/controlled_multi_cycle_runner.py | CREATE | Implement bounded deterministic multi-cycle runner and report builder. |
| docs/runbooks/cycle_runner.md | MODIFY | Document bounded multi-cycle loop and terminal stop behavior. |
| tests/test_roadmap_selector.py | MODIFY | Add deterministic multi-cycle selection-sequence proof test(s). |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add bounded stop/progress integrity multi-cycle tests. |
| tests/test_next_governed_cycle_runner.py | MODIFY | Add refusal/blocked-stop policy integration tests for multi-cycle control. |
| tests/test_system_cycle_operator.py | MODIFY | Add program/review constraint enforcement assertions during multi-cycle runs. |
| tests/test_system_mvp_validation.py | MODIFY | Add governed multi-cycle report contract and replay/trace linkage assertions. |
| tests/test_contracts.py | MODIFY | Include new report contract example validation coverage. |

## Contracts touched
- `contracts/schemas/multi_cycle_execution_report.schema.json` (new)
- `contracts/standards-manifest.json` (new contract entry pin)

## Tests that must pass after execution
1. `pytest tests/test_roadmap_selector.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_next_governed_cycle_runner.py`
4. `pytest tests/test_system_cycle_operator.py`
5. `pytest tests/test_system_mvp_validation.py`
6. `pytest tests/test_contracts.py`
7. `pytest tests/test_contract_enforcement.py`
8. `python scripts/run_contract_enforcement.py`
9. `.codex/skills/verify-changed-scope/run.sh` with `PLAN_FILES` set to this plan’s declared files

## Scope exclusions
- Do not redesign roadmap/control architecture.
- Do not introduce unbounded autonomous scheduling.
- Do not modify unrelated modules, schemas, or tests outside declared files.
- Do not alter downstream repository layouts.

## Dependencies
- Existing governed one-cycle seams remain authoritative (`run_system_cycle`, `run_next_governed_cycle`, roadmap selector/progress artifacts).
