# Plan — BAE Hardening Patch — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAE — Control Loop Integration hardening follow-up

## Objective
Apply a narrow fail-closed hardening patch to the BAE observe and enforcement paths without changing architecture or expanding scope.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAE-HARDENING-2026-03-22.md | CREATE | Required written plan before multi-file BUILD changes |
| contracts/schemas/evaluation_monitor_record.schema.json | MODIFY | Add healthy-status semantic guard (healthy implies valid + allow) for control-loop monitor records |
| contracts/schemas/evaluation_enforcement_action.schema.json | MODIFY | Add blocking-action reason constraint at the contract boundary |
| spectrum_systems/modules/runtime/evaluation_monitor.py | MODIFY | Harden fail-closed behavior in compute_alert_recommendation and assess_burn_rate |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Make unknown enforcement scope fail closed and enforce blocking-reasons invariant |
| tests/test_evaluation_monitor.py | MODIFY | Add fail-closed regressions for partial alert input and empty burn-rate input |
| tests/test_evaluation_control_loop.py | MODIFY | Add schema-semantic regression coverage for healthy/valid/allow consistency |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Add regressions for unknown-scope failure and blocking-empty-reasons rejection |

## Contracts touched
- `contracts/schemas/evaluation_monitor_record.schema.json` (semantic invariant hardening only; no shape expansion)
- `contracts/schemas/evaluation_enforcement_action.schema.json` (constraint hardening only; no shape expansion)

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_monitor.py tests/test_evaluation_control_loop.py tests/test_evaluation_enforcement_bridge.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not redesign monitor summaries or replay/decide logic.
- Do not add source_trace_ids or override schema changes.
- Do not modify legacy enforcement CLI paths.
- Do not perform broad refactors or unrelated cleanup.

## Dependencies
- Existing BAE/BAF control-loop and enforcement baseline artifacts remain authoritative.
