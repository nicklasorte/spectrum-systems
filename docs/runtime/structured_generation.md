# HS-X1 Structured Generation Boundary

## Purpose
HS-X1 hardens the AG runtime model boundary so structured steps bind to an explicit governed schema at generation time (or the closest strict adapter boundary) and fail closed when the claim cannot be honored.

## Structured generation semantics
- Structured generation is declared in `ai_model_request.structured_output`.
- Supported request modes:
  - `provider_native_strict`: provider-native schema-constrained output is required.
  - `adapter_json_schema_strict`: adapter-level strict JSON parsing + schema validation is required.
- Unstructured steps set `structured_output` to `null`.

## Target schema binding rules
- Structured requests must include `target_schema_ref` and it must resolve through governed contracts (`contracts/schemas/<name>.schema.json`).
- Vague JSON expectations are not allowed; runtime must declare the exact target schema contract name.
- AG model steps explicitly declare requirement via:
  - `requires_structured_generation` (boolean)
  - `structured_output` (object with mode + target schema)

## Provider-boundary enforcement rules
- Canonical adapter (`model_adapter.py`) is the single provider boundary.
- For `provider_native_strict`, provider capability is required (`supported_structured_modes` includes `provider_native_strict`), otherwise fail closed.
- For `adapter_json_schema_strict`, adapter requires JSON object output and validates the object against `target_schema_ref`.
- No silent downgrade to unconstrained free-form output.

## Fail-closed cases
Runtime/adapter fail closed on:
- missing structured declaration for required structured step
- missing/invalid target schema reference
- unknown schema reference
- provider incapable of required native structured mode
- malformed provider structured payload (non-JSON, non-object)
- schema mismatch between requested target and returned structured object
- canonical request/response contract validation failure

## Trace linkage
- `agent_execution_trace.model_invocations[*]` includes:
  - `structured_generation_mode`
  - `structured_target_schema_ref`
  - `structured_enforcement_path`
  - `structured_output_status`
- `ai_model_response.structured_output` records requested mode, target schema, enforcement path, and success/failure status.

## Determinism
- Structured request identity is included in canonical deterministic request ID derivation.
- Identical logical inputs produce identical canonical request payloads.
- Structured target linkage is explicit in canonical request, response, and execution trace.

## Explicitly out of scope in HS-X1
- routing policy redesign
- provider selection policy
- fallback orchestration
- broad multi-provider framework expansion
- streaming architecture redesign
- prompt-authoring redesign
