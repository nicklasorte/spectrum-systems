# Plan — BAG Legacy Replay Closure — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Prompt BAG — Replay Engine (Deterministic Control Replay)

## Objective
Close the remaining legacy replay seam by failing closed on ambiguous persistence, enforcing prerequisite hard-fail behavior in analysis flows, and removing post-validation mutation of execute_replay payloads.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAG-LEGACY-REPLAY-CLOSURE-2026-03-23.md | CREATE | Record the constrained execution plan before making a multi-file build change. |
| PLANS.md | MODIFY | Register this active plan in the plan index. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Fail closed for legacy persistence and remove decision-analysis mutation from execute_replay. |
| spectrum_systems/modules/runtime/replay_decision_engine.py | MODIFY | Enforce hard-fail replay prerequisite semantics in analysis flow and consume execute_replay safely. |
| tests/test_replay_engine.py | MODIFY | Add targeted coverage for legacy persistence fail-closed and execute_replay analysis guardrails. |
| tests/test_replay_decision_engine.py | MODIFY | Add targeted coverage for hard-fail analysis behavior and separation from legacy replay mutation. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py tests/test_replay_decision_engine.py`
2. `pytest -q`

## Scope exclusions
- Do not redesign replay_result schema.
- Do not change canonical `run_replay` behavior or weaken canonical validation.
- Do not refactor unrelated runtime modules.
- Do not introduce new replay artifact families.

## Dependencies
- Existing BAG replay engine canonical path and replay_result schema contracts remain authoritative.
