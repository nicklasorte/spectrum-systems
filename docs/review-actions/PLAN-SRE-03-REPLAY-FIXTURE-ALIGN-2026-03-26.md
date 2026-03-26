# Plan — SRE-03 Replay Fixture Alignment Follow-on — 2026-03-26

## Prompt type
PLAN

## Roadmap item
SRE-03 — Replay authoritative seam hardening follow-on fixture repair

## Objective
Repair stale replay_result test builders so drift-detection and regression-harness tests emit schema-valid replay_result v1.2.0 artifacts and reduce future contract drift risk via shared canonical builder usage.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-03-REPLAY-FIXTURE-ALIGN-2026-03-26.md | CREATE | Record required PLAN for multi-file test fixture/build changes. |
| PLANS.md | MODIFY | Register this active follow-on plan. |
| tests/helpers/replay_result_builder.py | CREATE | Shared canonical replay_result test builder to prevent fixture drift. |
| tests/test_drift_detection_engine.py | MODIFY | Replace stale inline replay_result fixture payload with shared canonical builder. |
| tests/test_replay_regression_harness.py | MODIFY | Replace stale replay_result builder with shared canonical builder and 1.2.0 contract fields. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_drift_detection_engine.py -q`
2. `pytest tests/test_replay_regression_harness.py -q`
3. `pytest tests/test_replay_engine.py -q`
4. `pytest -q`
5. `PLAN_FILES="docs/review-actions/PLAN-SRE-03-REPLAY-FIXTURE-ALIGN-2026-03-26.md PLANS.md tests/helpers/replay_result_builder.py tests/test_drift_detection_engine.py tests/test_replay_regression_harness.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify replay_result schema or standards manifest.
- Do not loosen fail-closed behavior in replay runtime modules.
- Do not add new runtime subsystems.

## Dependencies
- SRE-03 replay authoritative seam PR introducing replay_result schema_version `1.2.0` is already merged on current branch.
