# HS-03 Model Adapter Layer

## Purpose
HS-03 introduces a strict canonical boundary between AG runtime execution and provider-native model payloads.

Runtime/model interaction now uses two governed contracts:

- `ai_model_request`
- `ai_model_response`

Provider-native request/response payloads are contained inside `spectrum_systems.modules.runtime.model_adapter` and are not allowed to leak past that boundary.

## Canonical contracts

### `ai_model_request`
Required fields:

- `artifact_type`, `schema_version`
- `request_id`, `created_at`
- `prompt_id`, `prompt_version`
- `requested_model_id`
- `input_text`
- `execution_constraints` (`max_output_tokens`, `temperature`)
- `trace` (`trace_id`, `agent_run_id`, `step_id`)

### `ai_model_response`
Required fields:

- `artifact_type`, `schema_version`
- `response_id`, `created_at`
- `request_id`
- `provider_name`, `provider_model_name`
- `normalized_output_text`
- `finish_reason`, `response_status`
- `trace` (`trace_id`, `agent_run_id`, `step_id`)

Both schemas are strict (`additionalProperties: false`) and validated before crossing runtime boundaries.

## Adapter boundary rules

`CanonicalModelAdapter` enforces:

1. Validate canonical request against `ai_model_request`.
2. Convert canonical request -> minimal provider call shape.
3. Invoke provider adapter.
4. Normalize provider response -> canonical response.
5. Validate canonical response against `ai_model_response`.

AG runtime consumes only canonical response fields.

## Fail-closed behavior

The adapter fails closed for:

- Missing required canonical request fields.
- Non-object provider response payloads.
- Missing/empty provider output text.
- Missing provider model name.
- Unknown finish reasons.
- Canonical response contract validation failures.

No best-effort coercion is allowed.

## Trace linkage

`execute_step_sequence` now records `model_invocations` on `agent_execution_trace` with:

- `request_id`, `response_id`
- `requested_model_id`
- `provider_name`, `provider_model_name`
- `response_status`, `finish_reason`

This maintains deterministic lineage across:

`prompt_resolution -> ai_model_request -> ai_model_response -> agent_execution_trace`

## Explicitly out of scope

This HS-03 slice intentionally does **not** include:

- Routing policy
- Provider-selection policy
- Fallback orchestration
- Broad plugin framework / broad multi-provider abstraction
- Performance optimization
