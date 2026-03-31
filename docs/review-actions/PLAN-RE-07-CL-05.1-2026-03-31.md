# Plan — RE-07 CL-05.1 — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-07 CL-05.1 — Longitudinal Calibration Linkage Repair

## Objective
Repair CL-05 calibration-linkage validation so longitudinal calibration remains fail-closed and mandatory while matching governed judgment-enforcement compatibility.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RE-07-CL-05.1-2026-03-31.md | CREATE | Required plan-first artifact for CL-05.1 repair. |
| PLANS.md | MODIFY | Register active CL-05.1 repair plan. |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Refine calibration linkage validation to governed longitudinal model (not strict current-trace-only). |
| tests/test_control_loop.py | MODIFY | Add/adjust tests for repaired linkage semantics and fail-closed behavior. |
| tests/test_judgment_enforcement.py | MODIFY | Align canonical enforcement-path fixtures/assertions with repaired governed linkage model. |

## Contracts touched
None (repair aligns runtime linkage validation to existing CL-05 contracts).

## Tests that must pass after execution
1. `pytest tests/test_judgment_enforcement.py`
2. `pytest tests/test_judgment_learning.py`
3. `pytest tests/test_judgment_policy_lifecycle.py`
4. `pytest tests/test_control_loop.py`
5. `pytest tests/test_evaluation_control.py`
6. `pytest tests/test_drift_detection.py`
7. `pytest tests/test_drift_remediation.py`

## Scope exclusions
- Do not weaken CL-05 calibration authority to advisory-only behavior.
- Do not redesign control-loop architecture.
- Do not modify CL-01..CL-04 semantics outside narrow CL-05 compatibility repair.
- Do not start NX work.

## Dependencies
- Existing RE-07 CL-05 implementation commit must be present.
- Existing judgment-learning, control-loop, and enforcement seams remain authoritative.
