# HS-04 Routing Policy Engine

## Purpose
HS-04 introduces an artifact-first routing policy boundary for AG runtime.
Routing now resolves prompt alias/version and selected model id through an explicit governed policy decision artifact (`routing_decision`) instead of implicit runtime defaults.

## Contracts

### `routing_policy` (`contracts/schemas/routing_policy.schema.json`)
Deterministic governed policy input artifact.

Required fields:
- `artifact_type` = `routing_policy`
- `schema_version` = `1.0.0`
- `policy_id`
- `created_at`
- `policy_scope` = `ag_runtime`
- `model_catalog` (allow-list of model ids)
- `routes` (bounded deterministic route entries)

Route selectors are intentionally narrow:
- `route_key` (required)
- `task_class` (optional exact-match refinement)

Each route deterministically declares:
- `risk_class`
- `prompt_selection.prompt_id`
- `prompt_selection.prompt_alias`
- `model_selection.selected_model_id`

### `routing_decision` (`contracts/schemas/routing_decision.schema.json`)
Deterministic emitted runtime routing artifact.

Required fields include:
- `artifact_type`, `schema_version`
- `routing_decision_id`, `created_at`
- `route_key`, `task_class`, `risk_class`
- `selected_prompt_id`, `selected_prompt_alias`, `resolved_prompt_version`
- `selected_model_id`
- `policy_id`
- `trace.trace_id`, `trace.agent_run_id`
- `related_artifact_refs`

## Resolution Rules
1. Load and schema-validate `routing_policy`.
2. Match runtime (`route_key`, `task_class`) against policy routes.
3. Require **exactly one** matching route.
4. Resolve selected prompt via HS-01 prompt registry (`prompt_alias_map` + immutable entries).
5. Validate selected model id is allow-listed in `model_catalog`.
6. Emit `routing_decision` with deterministic id/timestamp derived only from canonical routing inputs.

## Fail-Closed Behavior
The runtime halts routing on any of the following:
- Unknown `route_key` / no route match.
- Ambiguous route match (more than one match).
- Invalid/missing prompt alias resolution.
- Invalid selected model id outside policy allow-list.
- Malformed or schema-invalid policy artifact.

No implicit defaults, no fallback model/prompt selection, no reuse of prior model selection state.

## Runtime Integration
AG runtime (`agent_golden_path`) now emits and links:
1. `routing_decision`
2. `agent_execution_trace.prompt_resolution`
3. `agent_execution_trace.model_invocations` (canonical request/response ids)

`agent_execution_trace.routing_decision` contains routing linkage keys:
- `routing_decision_id`
- `policy_id`
- `route_key`
- `task_class`
- `selected_model_id`

## Relationship to HS-01 and HS-03
- HS-01 remains the authoritative prompt alias/version resolver.
- HS-03 remains the canonical model adapter boundary.
- HS-04 only governs deterministic selection inputs into those two boundaries.

## Out of Scope for HS-04
- Dynamic optimization or live cost/latency switching.
- Probabilistic routing.
- Fallback chains/orchestration.
- Canary or release strategy logic.
- UI/policy editing workflows.
