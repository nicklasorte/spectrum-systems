# AG-07 Controlled Generated Eval Promotion

## Why this is high-authority
Promotion moves a generated eval from candidate execution artifact state into durable required execution coverage. This can directly change progression gates, so the path is explicit, deterministic, and fail-closed.

## Required artifacts
A generated eval can only be promoted when all governed artifacts exist:

1. `generated_eval_case`
2. `generated_eval_admission_record` with `admitted=true`
3. candidate/staging artifact (`generated_eval_candidate_record`)
4. `generated_eval_promotion_request_record`
5. `generated_eval_promotion_decision_record`
6. `generated_eval_promotion_result_record` (gate output)

Rollback uses `generated_eval_promotion_rollback_record`.

## Promotion gate conditions
Promotion blocks unless all conditions are true:

- generated eval case exists
- admission exists and is admitted
- candidate record exists
- occurrence count meets threshold
- promotion request exists
- promotion decision exists
- decision is `approved`
- replay validation passes

If any condition fails, the gate emits `generated_eval_promotion_result_record` with `promoted=false` and explicit `blocked_reasons`.

## Replay validation requirement
Before promotion, replay validation checks deterministic linkage:

- `expected_reason_code` equals `reason_code`
- `expected_outcome` is bounded and reason-linked
- source failure lineage in the eval case appears in promotion request lineage

Replay failure blocks promotion with `replay_validation_passed=false`.

## Controlled required-eval update path
There is one controlled mutation path: `execute_generated_eval_promotion_gate(...)`.

When promotion is approved and replay-valid, this path updates:

- `required_eval_registry.mappings[artifact_family=generated_eval_case].required_evals`

The promotion result records this target in `required_eval_target`.

## Rollback semantics
Rollback is explicit and auditable:

- `execute_generated_eval_promotion_rollback(...)` emits `generated_eval_promotion_rollback_record`
- removes the promoted generated eval from the controlled required-eval target
- keeps deterministic IDs and lineage references

## Non-negotiable guardrail
Occurrence threshold alone never promotes anything. Promotion always requires explicit request and decision artifacts plus replay validation.
