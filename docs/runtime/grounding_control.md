# HS-20 Grounding Control Gate

## Purpose
HS-20 converts HS-19 `grounding_factcheck_eval` from passive observation into an active deterministic enforcement control artifact: `grounding_control_decision`.

## Relationship to HS-19
- HS-19 remains the only grounding evaluator.
- HS-20 does **not** change HS-19 evaluator logic or failure classes.
- HS-20 consumes HS-19 claim-level outputs and maps them into runtime control status and enforcement action.

## Decision rules (v1)
Given HS-19 claim results:
1. If `invalid_evidence_refs > 0` → `status = block`
2. Else if `unsupported_claims > 0` → `status = warn`
3. Else → `status = pass`

## Enforcement mapping
- `pass` → `allow`
- `warn` → `flag`
- `block` → `block_execution`

## Runtime enforcement semantics
In agent execution:
- `block_execution`: execution terminates fail-closed before downstream validation stages continue.
- `flag`: execution continues, and warning state is persisted in trace `failure_reason`.
- `allow`: execution continues with no warning reason.

## Determinism guarantees
- Control decision ID is deterministic from normalized payload (`deterministic_id`).
- Timestamp uses HS-19 timestamp when valid, otherwise deterministic fallback.
- Rule application is deterministic and order-stable.
- Output contract is schema-validated prior to return.

## Failure modes
- Malformed HS-19 eval input triggers fail-closed control decision:
  - `status = block`
  - `enforcement_action = block_execution`
  - `triggered_rules = ["malformed_eval_input"]`
- Any schema validation failure in control decision generation is raised as runtime error and treated as fail-closed by upstream runtime handling.

## Trace linkage
- `multi_pass_generation_record.grounding_control_decision` carries full governed decision artifact.
- `agent_execution_trace.multi_pass_generation.grounding_control_decision` propagates decision linkage (`decision_id`, `status`, `enforcement_action`, `triggered_rules`) for runtime auditability.
