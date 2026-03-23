# Plan — BAF Deterministic Identity Hotfix — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Prompt BAF — Enforcement Wiring trust-boundary remediation (targeted hotfix)

## Objective
Make governed enforcement/control identity surfaces deterministic for semantically identical inputs while preserving fail-closed behavior.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/enforcement_engine.py | MODIFY | Remove random/time-derived governed enforcement IDs and use deterministic canonical identity payload hashing. |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Remove current-time-derived linkage behavior from failure_eval_case decision identity path. |
| tests/test_enforcement_engine.py | MODIFY | Add deterministic regression coverage for governed enforcement IDs and timestamp independence. |
| tests/test_evaluation_control.py | MODIFY | Add focused deterministic coverage for semantically stable decision IDs independent of non-semantic timestamp changes. |
| tests/test_control_loop.py | MODIFY | Add targeted deterministic failure_eval_case control-loop identity regression coverage. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_enforcement_engine.py tests/test_evaluation_control.py`
2. `pytest tests/test_control_loop.py`

## Scope exclusions
- Do not redesign replay architecture.
- Do not modify schemas or standards manifests.
- Do not refactor unrelated runtime modules.

## Dependencies
- None.
