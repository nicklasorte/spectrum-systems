# AG-05 Failure → Eval Auto-Generation

## Purpose
AG-05 converts bounded governed runtime failure/control outcomes into deterministic `failure_eval_case` artifacts so blocked outcomes can be replayed and regressed as first-class eval inputs.

## Source conditions in scope
Auto-generation is intentionally narrow and only runs for these source artifact classes:

1. `agent_failure_record`
   - Condition: governed AG runtime stage failure artifact exists.
2. `hitl_review_request`
   - Condition: `trigger_reason` is one of:
     - `indeterminate_outcome_routed_to_human`
     - `policy_review_required`
     - `control_non_allow_response`
3. `evaluation_control_decision`
   - Condition: decision is non-allow and reusable as a failure pattern:
     - `decision = "deny"`, or
     - `decision = "require_review"` with indeterminate rationale.

Out of scope: opportunistic generation from arbitrary logs/events or unsupported artifact types.

## Artifact shape
Contract: `contracts/schemas/failure_eval_case.schema.json` (`schema_version = 1.1.0`).

Required fields:
- identity/timing: `eval_case_id`, `created_at`
- linkage: `source_run_id`, `trace_id`, `source_artifact_type`, `source_artifact_id`
- failure semantics: `failure_class`, `failure_stage`, `triggering_condition`
- bounded context: `normalized_inputs`
- evaluation intent: `expected_system_behavior`, `observed_system_behavior`, `evaluation_goal`, `pass_criteria`
- provenance: `provenance.source_artifact_ref`, generation path/module metadata

All objects use `additionalProperties: false`.

## Determinism rules
- `eval_case_id` is deterministic (`deterministic_id`) from canonical source linkage + condition tuple.
- `created_at` is deterministic from a canonical hash-derived timestamp seed.
- same source artifact + same normalized context ⇒ byte-stable artifact output.
- no random IDs and no free-form narrative extraction from logs.

## Fail-closed behavior
- At runtime control boundary (`enforce_control_before_execution`), blocked execution requiring AG-05 generation fails closed if generation fails.
- Failure to emit required `failure_eval_case` raises a governed runtime error (`ContractRuntimeError`), preventing silent continuation.

## Replay/regression compatibility
`failure_eval_case` provides deterministic replay linkage via:
- `source_run_id`
- `trace_id`
- `source_artifact_type`
- `source_artifact_id`
- provenance source reference

This shape is designed for deterministic downstream ingestion by replay/eval registry workflows (including AG-07 follow-on work).
