# Plan — CL Review Fixes (CL-1..CL-4) — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt BAF — Enforcement Wiring (single-path evaluation_control_decision enforcement)

## Objective
Implement only the blocking control-loop enforcement fixes CL-1 through CL-4 so continuation is fail-closed, decision IDs are deterministic, and replay uses canonical control-loop enforcement.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CL-REVIEW-FIXES-2026-03-22.md | CREATE | Required PLAN artifact for a >2 file BUILD scope. |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | CL-1 allowlist continuation gate; CL-4 orphaned bypass artifact cleanup. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | CL-2 deterministic decision_id generation from stable inputs. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | CL-3 canonical replay path via run_control_loop → enforce_control_decision. |
| tests/test_control_integration.py | MODIFY | CL-1 test coverage for None/missing/unknown/success statuses and CL-4 cleanup. |
| tests/test_evaluation_control.py | MODIFY | CL-2 deterministic decision_id repeatability tests. |
| tests/test_replay_engine.py | MODIFY | CL-3 replay assertions for canonical enforcement artifacts, no legacy dependency. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_control_integration.py`
2. `pytest tests/test_evaluation_control.py`
3. `pytest tests/test_replay_engine.py`
4. `pytest tests/test_enforcement_engine.py`
5. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/check_artifact_boundary.py`
8. `pytest`

## Scope exclusions
- Do not implement optional/non-blocking review recommendations.
- Do not modify schemas or contract versions.
- Do not add new replay architecture beyond canonical control-loop enforcement wiring.
- Do not refactor unrelated runtime or test modules.

## Dependencies
- Existing BAF/BAE control loop and enforcement contracts must remain authoritative.
