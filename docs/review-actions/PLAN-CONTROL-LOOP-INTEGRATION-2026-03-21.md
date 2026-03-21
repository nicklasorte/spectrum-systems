# Plan — CONTROL LOOP INTEGRATION — 2026-03-21

## Prompt type
PLAN

## Roadmap item
Prompt CONTROL LOOP INTEGRATION — MVP Phase 2

## Objective
Wire run-bundle validation decisions into a deterministic, schema-validated control loop that emits evaluation_monitor_record, evaluation_monitor_summary, and evaluation_budget_decision artifacts with enforcement-ready responses.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CONTROL-LOOP-INTEGRATION-2026-03-21.md | CREATE | Required plan-first artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register the active control-loop plan in the plan index table. |
| contracts/schemas/evaluation_monitor_record.schema.json | MODIFY | Extend contract to validate run-bundle monitor record shape while preserving existing monitor record compatibility. |
| contracts/schemas/evaluation_monitor_summary.schema.json | MODIFY | Extend contract to validate run-bundle monitor summary shape while preserving existing monitor summary compatibility. |
| contracts/schemas/evaluation_budget_decision.schema.json | MODIFY | Extend contract to validate enforcement-ready budget decision shape for control-loop outputs while preserving existing compatibility. |
| contracts/examples/evaluation_monitor_record.json | CREATE | Publish a canonical example for the control-loop monitor record contract branch. |
| contracts/examples/evaluation_monitor_summary.json | CREATE | Publish a canonical example for the control-loop monitor summary contract branch. |
| contracts/examples/evaluation_budget_decision.json | CREATE | Publish a canonical example for the control-loop budget decision contract branch. |
| spectrum_systems/modules/runtime/evaluation_monitor.py | MODIFY | Add pure control-loop monitor record + summary builders for artifact_validation_decision ingestion and aggregation. |
| spectrum_systems/modules/runtime/evaluation_budget_governor.py | MODIFY | Add pure control-loop budget decision builder from monitor summary with fail-closed mapping. |
| scripts/run_evaluation_control_loop.py | CREATE | Add thin CLI wrapper that wires validator -> monitor -> summary -> budget decision with deterministic exit codes. |
| tests/test_evaluation_control_loop.py | CREATE | Add deterministic unit + end-to-end tests for control-loop mapping, fail-closed behavior, and CLI exits. |
| contracts/standards-manifest.json | MODIFY | Publish updated schema versions for modified contracts and bump standards metadata. |

## Contracts touched
- `contracts/schemas/evaluation_monitor_record.schema.json`
- `contracts/schemas/evaluation_monitor_summary.schema.json`
- `contracts/schemas/evaluation_budget_decision.schema.json`
- `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `python scripts/verify_environment.py`
2. `pytest tests/test_run_bundle_validation.py -q`
3. `pytest tests/test_run_bundle_validator.py -q`
4. `pytest tests/test_evaluation_control_loop.py -q`
5. `pytest -q`
6. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`

## Scope exclusions
- Do not refactor existing evaluation monitor/governor legacy policy logic outside required extensions.
- Do not modify enforcement bridge behavior beyond compatibility with new decision schema values.
- Do not alter unrelated control-chain modules.

## Dependencies
- Existing run-bundle validator (`spectrum_systems/modules/runtime/run_bundle_validator.py`) remains authoritative for artifact validation decisions.
