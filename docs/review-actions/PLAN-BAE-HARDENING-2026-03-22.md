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
| PLANS.md | MODIFY | Register the new active plan |
| spectrum_systems/modules/runtime/evaluation_monitor.py | MODIFY | Add fail-closed ID guards in control-loop observe record construction |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Add blocking/allowed invariant guard in build_enforcement_action |
| scripts/run_evaluation_enforcement_bridge.py | MODIFY | Add CLI fail-closed catch-all on allowed_to_proceed=false |
| contracts/schemas/evaluation_enforcement_action.schema.json | MODIFY | Encode action_type/allowed_to_proceed invariants at contract boundary |
| tests/test_evaluation_control_loop.py | MODIFY | Add regression coverage for missing run_id/trace_id/decision_id failures |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Add regression coverage for enforcement invariant and CLI catch-all |

## Contracts touched
- `contracts/schemas/evaluation_enforcement_action.schema.json` (constraint hardening only; no shape expansion)

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_control_loop.py tests/test_evaluation_enforcement_bridge.py`
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
