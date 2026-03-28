# Plan — PQX-QUEUE-04B — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-04] Unified Transition Policy and Next-Step Decision Spine
Repair Slice: QUEUE-04B — Legacy Queue-Integration Semantics Compatibility

## Objective
Preserve QUEUE-04 unified transition architecture while restoring legacy queue/work-item mutation behavior and fail-closed error surfaces for legacy integration APIs and tests.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-04B-2026-03-28.md | CREATE | Required PLAN artifact for repair slice. |
| PLANS.md | MODIFY | Register active QUEUE-04B plan. |
| spectrum_systems/modules/prompt_queue/next_step_orchestrator.py | MODIFY | Restore legacy orchestration semantics via compatibility path while preserving transition-artifact mode. |
| spectrum_systems/modules/prompt_queue/next_step_queue_integration.py | MODIFY | Restore legacy queue mutation integration with transition-compatible validation and preserve read-only emit API. |
| spectrum_systems/modules/prompt_queue/post_execution_queue_integration.py | MODIFY | Restore legacy post-execution queue mutation semantics with transition-compatible validation. |
| spectrum_systems/modules/prompt_queue/loop_control_queue_integration.py | MODIFY | Restore legacy loop-control queue mutation semantics with fail-closed tuple validation. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Re-export restored legacy integration functions from module seams. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_next_step.py tests/test_prompt_queue_post_execution.py`
2. `pytest tests/test_prompt_queue_transition_decision.py tests/test_prompt_queue_post_execution_policy.py tests/test_prompt_queue_next_step_integration.py`

## Scope exclusions
- Do not remove `prompt_queue_transition_decision` schema or builder.
- Do not implement queue loop orchestration.
- Do not alter retry/replay/certification behavior.

## Dependencies
- QUEUE-04 and QUEUE-04A completed.
