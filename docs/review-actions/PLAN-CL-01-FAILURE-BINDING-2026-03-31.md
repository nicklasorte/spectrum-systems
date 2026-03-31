# Plan — CL-01 Failure Binding — 2026-03-31

## Prompt type
PLAN

## Roadmap item
CL-01 — Failure Binding

## Objective
Ensure every governed failure deterministically yields a failure eval case that is policy-bound, registry-tracked, and consumable by the control loop with fail-closed blocking when any binding step is missing.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/evaluation_auto_generation.py | MODIFY | Add deterministic failure classification, policy binding metadata, and explicit fail-closed binding validation. |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Accept failure_eval_case signals and enforce control decision consumption path for failure-derived evals. |
| tests/test_agent_failure_artifacts.py | MODIFY | Add CL-01 assertions that failure flow emits deterministically bound failure eval artifacts. |
| tests/test_evaluation_control.py | MODIFY | Add policy binding fail-closed tests for failure_eval_case decision generation. |
| tests/test_control_loop.py | MODIFY | Add control-loop tests verifying failure-eval consumption and blocking semantics. |
| docs/review-actions/PLAN-CL-01-FAILURE-BINDING-2026-03-31.md | CREATE | Required PLAN artifact for multi-file CL-01 execution scope. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_agent_failure_artifacts.py`
2. `pytest tests/test_evaluation_control.py`
3. `pytest tests/test_judgment_learning.py`
4. `pytest tests/test_control_loop.py`

## Scope exclusions
- Do not implement CL-02 or any later control-loop closure slice.
- Do not modify roadmap authority files.
- Do not redesign runtime architecture beyond existing failure/eval/policy/control seams.
- Do not modify unrelated modules or test surfaces.

## Dependencies
- RE-07 authorization for CL-01 only.
