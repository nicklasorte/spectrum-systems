# Plan — BATCH-SYS-ENF-03 — 2026-04-09

## Prompt type
BUILD

## Roadmap item
BATCH-SYS-ENF-03

## Objective
Enforce that promotion and closure authority is only sourced from CDE closure decision artifacts while all other modules emit non-authoritative signals and fail closed when required artifacts are missing.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SYS-ENF-03-2026-04-09.md | CREATE | Required execution plan for multi-file governance change. |
| spectrum_systems/modules/review_promotion_gate.py | MODIFY | Remove promotion decisions and require closure_decision_artifact input. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Remove non-CDE promotion authority and require CDE closure artifact for promoted transitions. |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY | Downgrade to recommendation-only artifact and require FRE artifact reference for repair plans. |
| spectrum_systems/orchestration/fix_plan.py | MODIFY | Remove local repair plan synthesis and enforce FRE-produced artifact consumption. |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Remove local TPA decisioning and require precomputed TPA artifact evidence. |
| contracts/schemas/review_promotion_gate_artifact.schema.json | MODIFY | Remove decision semantics and enforce signal-only shape. |
| contracts/schemas/next_step_decision_artifact.schema.json | MODIFY | Remove authoritative decision fields and enforce recommendation-only fields. |
| contracts/schemas/fix_plan_artifact.schema.json | MODIFY | Align with FRE-produced fix plan authority constraints. |
| tests/test_review_promotion_gate.py | MODIFY | Update expected signal-only review gate behavior. |
| tests/test_sequence_transition_policy.py | MODIFY | Validate CDE-only promotion requirements and fail-closed behavior. |
| tests/test_next_step_decision.py | MODIFY | Validate recommendation-only next-step outputs and FRE artifact requirements. |
| tests/test_fix_plan.py | MODIFY | Validate FRE artifact requirement and no local generation path. |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Validate TPA artifact precondition and fail-closed checks. |

## Contracts touched
- review_promotion_gate_artifact.schema.json
- next_step_decision_artifact.schema.json
- fix_plan_artifact.schema.json

## Tests that must pass after execution
1. `pytest tests/test_review_promotion_gate.py tests/test_sequence_transition_policy.py tests/test_next_step_decision.py tests/test_fix_plan.py tests/test_evaluation_enforcement_bridge.py`

## Scope exclusions
- Do not redesign orchestration state machine beyond authority/fail-closed constraints.
- Do not add new runtime systems beyond wiring to existing CDE/FRE/TPA artifacts.
- Do not modify unrelated docs or contracts outside targeted authority enforcement.

## Dependencies
- None
