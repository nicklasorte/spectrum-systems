# Plan — PQX Control-Loop Trust Boundary Review Fixes — 2026-03-27

## Prompt type
PLAN

## Roadmap item
PQX review-fix hardening slice (control-loop trust boundary)

## Objective
Resolve highest-priority Claude review findings for control-loop trust-boundary behavior while preserving fail-closed semantics and deterministic contracts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-CONTROL-LOOP-TRUST-BOUNDARY-REVIEW-FIXES-2026-03-27.md | CREATE | Required PLAN artifact for this multi-file hardening slice |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Remove unreachable `deny_indeterminate_failure` logic in implementation |
| contracts/schemas/evaluation_control_decision.schema.json | MODIFY | Remove dead rationale enum vocabulary and align contract with implementation |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | Preserve blocked integration_result on secondary eval-case generation failure; tighten `require_review` blocked semantics |
| spectrum_systems/modules/runtime/control_loop_chaos.py | MODIFY | Require explicit `expected_decision`; enforce exact reason matching by default with explicit opt-in for extras |
| tests/test_evaluation_control.py | MODIFY | Add/adjust tests for indeterminate rationale routing |
| tests/test_control_integration.py | MODIFY | Add/adjust tests for blocked-path eval-case-generation failure behavior and require_review blocking semantics |
| tests/test_control_loop_chaos.py | MODIFY | Add tests for required `expected_decision` and exact reason matching behavior |
| docs/review-actions/2026-03-27-control-loop-trust-boundary-review-actions.md | MODIFY | Mark implemented review actions as closed |
| docs/reviews/2026-03-27-control-loop-trust-boundary-review.md | MODIFY | Add short closure note summarizing materially resolved conclusions |

## Contracts touched
- `contracts/schemas/evaluation_control_decision.schema.json` (enum alignment to remove unreachable rationale code)

## Tests that must pass after execution
1. `pytest tests/test_control_integration.py`
2. `pytest tests/test_control_loop.py`
3. `pytest tests/test_control_loop_chaos.py`
4. `pytest tests/test_evaluation_control.py`
5. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not modify unrelated runtime modules outside the review-specified surface.
- Do not introduce new feature surfaces or policy semantics.
- Do not relax schema validation or fail-closed execution behavior.

## Dependencies
- Source review artifact and action tracker dated 2026-03-27 are authoritative inputs.
