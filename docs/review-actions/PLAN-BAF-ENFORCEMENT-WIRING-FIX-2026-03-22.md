# Plan — BAF Enforcement Wiring Trust-Boundary Fix — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt BAF — Enforcement Wiring (MVP Phase 3)

## Objective
Restore fail-closed enforcement boundaries across replay and control integration by removing fail-open paths, hardening status translation, and preventing malformed provenance collisions.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAF-ENFORCEMENT-WIRING-FIX-2026-03-22.md | CREATE | Required plan-first artifact for this trust-boundary remediation. |
| PLANS.md | MODIFY | Register this active plan in plan tracking. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Remove replay fail-open catch-all and propagate enforcement/control loop failures as hard replay errors. |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | Enforce strict governed artifact boundary and explicit final_status mapping guard. |
| spectrum_systems/modules/runtime/enforcement_engine.py | MODIFY | Add explicit deprecation warning on legacy enforcement path. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Prevent malformed-input decision_id collisions while keeping valid deterministic IDs unchanged. |
| tests/test_replay_engine.py | MODIFY | Add replay failure propagation assertions for enforcement and control loop errors. |
| tests/test_control_integration.py | MODIFY | Add unsupported artifact/non-dict rejection and unknown final_status guard assertions. |
| tests/test_enforcement_engine.py | MODIFY | Verify legacy enforcement path deprecation warning and non-test caller guard strategy. |
| tests/test_evaluation_control.py | MODIFY | Verify malformed inputs without eval_run_id generate distinct decision_ids. |
| docs/reviews/BAF_enforcement_wiring_fix_report.md | CREATE | Required implementation report artifact for Claude review closure. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_replay_engine.py`
2. `pytest -q tests/test_control_integration.py`
3. `pytest -q tests/test_enforcement_engine.py`
4. `pytest -q tests/test_evaluation_control.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add new artifact types or schemas.
- Do not expand architecture beyond BAF enforcement wiring trust-boundary fixes.
- Do not refactor unrelated runtime modules.

## Dependencies
- Existing BAE/BAF/BAG control-loop and enforcement schemas remain authoritative and unchanged.
