# Plan — PQX-QUEUE-04A — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-04] Unified Transition Policy and Next-Step Decision Spine
Repair Slice: QUEUE-04A — Export Compatibility Fix

## Objective
Restore package-level prompt queue compatibility exports and legacy-call compatibility shims without rolling back the unified transition spine or reintroducing queue advancement behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-04A-2026-03-28.md | CREATE | Required PLAN artifact for multi-file repair slice. |
| PLANS.md | MODIFY | Register active QUEUE-04A plan. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Restore compatibility exports for apply_* queue integration symbols. |
| spectrum_systems/modules/prompt_queue/next_step_orchestrator.py | MODIFY | Add thin legacy argument compatibility for determine_next_step_action while preserving transition spine. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_next_step.py tests/test_prompt_queue_post_execution.py`
2. `pytest tests/test_prompt_queue_transition_decision.py tests/test_prompt_queue_post_execution_policy.py tests/test_prompt_queue_next_step_integration.py`

## Scope exclusions
- Do not remove or bypass unified transition decision artifact.
- Do not reintroduce queue loop orchestration.
- Do not add queue state mutation logic to transition integrations.
- Do not alter retry/replay/certification behavior.

## Dependencies
- QUEUE-04 unified transition spine remains authoritative.
