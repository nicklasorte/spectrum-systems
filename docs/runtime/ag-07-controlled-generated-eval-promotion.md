# AG-07 Controlled Generated Eval Required-Registry Change

## Why this remains high-impact
This path updates durable required eval coverage for generated eval candidates. Because coverage changes affect progression checks, the path is explicit, deterministic, and fail-closed.

## Required artifacts
A generated eval required-registry change requires all governed artifacts:

1. `generated_eval_case`
2. `generated_eval_admission_record` with `admitted=true`
3. candidate/staging artifact (`generated_eval_candidate_record`)
4. `generated_eval_registry_change_request_record`
5. `generated_eval_registry_change_review_record`
6. `generated_eval_registry_change_execution_record` (gate output)

Reversal uses `generated_eval_registry_change_reversal_record`.

## Registry-change gate conditions
Registry change blocks unless all conditions are true:

- generated eval case exists
- admission exists and is admitted
- candidate record exists and links to the same generated eval artifact
- occurrence count meets threshold
- registry-change request exists
- registry-change review exists
- review outcome is `ready`
- replay validation passes

If any condition fails, the gate emits `generated_eval_registry_change_execution_record` with `registry_updated=false` and explicit `blocked_reasons`.

## Replay validation requirement
Before registry update, replay validation checks deterministic linkage:

- `expected_reason_code` equals `reason_code`
- `expected_outcome` is bounded and its reason-code suffix equals `expected_reason_code`
- source failure lineage in the eval case appears in request lineage

Replay failure blocks registry updates with `replay_validation_passed=false`.

## One-path required-eval update rule
There is one controlled mutation path: `execute_generated_eval_registry_change_gate(...)`.

When review outcome is ready and replay-valid, this path updates:

- `required_eval_registry.mappings[artifact_family=generated_eval_case].required_evals`

The execution artifact records this target in `required_eval_target`.

## Reversal semantics
Reversal is explicit and auditable:

- `execute_generated_eval_registry_change_reversal(...)` emits `generated_eval_registry_change_reversal_record`
- removes the generated eval entry from the same required-eval target
- keeps deterministic IDs and lineage references

## Non-negotiable guardrail
Occurrence threshold alone never updates required eval coverage. Explicit request and explicit review artifacts are required.
