# Plan — SRE-03 Replay Enforcement Completion — 2026-03-26

## Prompt type
PLAN

## Roadmap item
SRE-03

## Objective
Enforce replay_result as the single authoritative input boundary for downstream runtime monitor/decision/alert paths with strict fail-closed rejection of non-replay or partial replay inputs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-03-REPLAY-ENFORCEMENT-COMPLETION-2026-03-26.md | CREATE | Record PLAN for this multi-file SRE-03 enforcement slice before BUILD changes. |
| PLANS.md | MODIFY | Register the new active SRE-03 plan in the active-plan table. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Enforce replay_result-only decision input and fail-closed boundary checks. |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Restrict control-loop ingestion to replay_result and remove non-replay signal routes. |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | Restrict supported governed artifact type to replay_result. |
| spectrum_systems/modules/runtime/alert_triggers.py | MODIFY | Harden replay_result boundary checks for required embedded artifacts and trace linkage. |
| spectrum_systems/modules/runtime/evaluation_monitor.py | MODIFY | Add replay-boundary validation for monitor ingestion paths. |
| tests/test_evaluation_control.py | MODIFY | Update/add tests for replay-only and partial replay fail-closed behavior. |
| tests/test_control_loop.py | MODIFY | Update/add tests proving non-replay and partial replay inputs are rejected. |
| tests/test_alert_triggers.py | MODIFY | Add regression tests for missing replay artifacts and trace-linkage rejection. |
| tests/test_evaluation_monitor.py | MODIFY | Add replay boundary enforcement and bypass-prevention tests. |
| SYSTEMS.md | MODIFY | Add short replay-only runtime invariant note. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_evaluation_control.py tests/test_control_loop.py tests/test_alert_triggers.py tests/test_evaluation_monitor.py`
2. `pytest tests/test_replay_engine.py`

## Scope exclusions
- Do not introduce new runtime subsystems.
- Do not broaden schema surface beyond strict replay enforcement needs.
- Do not refactor unrelated runtime modules or unrelated test suites.

## Dependencies
- docs/review-actions/PLAN-SRE-03-REPLAY-CONTRACT-BOUNDARY-HARDENING-2026-03-26.md must be complete enough to provide existing replay contract assumptions.
