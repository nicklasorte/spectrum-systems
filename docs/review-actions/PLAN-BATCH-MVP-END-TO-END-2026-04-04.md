# Plan — BATCH-MVP-END-TO-END — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-MVP-END-TO-END — Full Roadmap Execution (Control-Governed)

## Objective
Enable deterministic full-roadmap execution that continues only on control decisions `allow|warn`, stops fail-closed on `freeze|block` or invalid/missing control signals, and emits a governed full execution report contract.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-MVP-END-TO-END-2026-04-04.md | CREATE | Required plan artifact before multi-file BUILD execution. |
| PLANS.md | MODIFY | Register this active plan in the plan index. |
| contracts/schemas/roadmap_execution_report.schema.json | CREATE | Contract-first definition for full-run roadmap execution report. |
| contracts/examples/roadmap_execution_report.json | CREATE | Golden-path deterministic example for new contract. |
| contracts/standards-manifest.json | MODIFY | Add canonical contract registration for `roadmap_execution_report`. |
| spectrum_systems/modules/runtime/controlled_multi_cycle_runner.py | MODIFY | Add `run_full_roadmap_execution` and strict continuation/stop behavior. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add full-run coverage tests (allow/warn continue, freeze/block stop, deterministic sequence, report correctness). |
| tests/test_contracts.py | MODIFY | Validate new contract example in contract test surface. |
| tests/test_system_mvp_validation.py | MODIFY | Add explicit validation test for new contract example. |

## Contracts touched
- Create `roadmap_execution_report` in `contracts/schemas/roadmap_execution_report.schema.json`.
- Register `roadmap_execution_report` in `contracts/standards-manifest.json`.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_multi_batch_executor.py`
2. `pytest tests/test_contracts.py tests/test_system_mvp_validation.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh --base HEAD~1 --head HEAD`

## Scope exclusions
- Do not modify unrelated runtime modules outside multi-cycle/full-run execution logic.
- Do not change roadmap selection semantics outside required stop/continue governance behavior.
- Do not alter unrelated contracts, schemas, or test suites.

## Dependencies
- Existing controlled single/multi-cycle runtime seams (`run_system_cycle`, `run_controlled_multi_cycle`) remain authoritative and are reused.
