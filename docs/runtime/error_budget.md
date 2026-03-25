# Error Budget Status (SRE-09)

## What this artifact means in this repo
`error_budget_status` is the governed measurement artifact that converts a deterministic `service_level_objective` + `observability_metrics` pair into explicit budget-consumption state.

This slice is measurement/governance only. It does not trigger alerting, blocking, or notification behavior.

## Contracts and policy
- `contracts/schemas/error_budget_status.schema.json`
- `contracts/examples/error_budget_status.json`
- `contracts/schemas/error_budget_policy.schema.json`
- `contracts/examples/error_budget_policy.json`

## Supported metric vocabulary
The budget model is intentionally bounded to existing SLO/observability metrics:
- `replay_success_rate`
- `grounding_block_rate`
- `unsupported_claim_rate`
- `invalid_evidence_ref_rate`
- `drift_exceed_threshold_rate`
- `baseline_gate_block_rate`
- `regression_failure_rate`

Unknown metrics fail closed.

## Deterministic computation semantics
For each SLO objective:
1. Validate governed inputs (`service_level_objective`, `observability_metrics`, optional `error_budget_policy`).
2. Require the metric to be both policy-supported and present in `observability_metrics.metrics`.
3. Compute:
   - `allowed_error`
   - `consumed_error`
   - `remaining_error`
   - `consumption_ratio`
4. Map objective status from `consumption_ratio` using policy thresholds:
   - `healthy`
   - `warning`
   - `exhausted`
5. Derive overall `budget_status` and `highest_severity` as the max objective severity.

Artifact identity (`artifact_id`) is deterministic SHA-256 over canonical JSON preimage.

## Status semantics
- `healthy`: consumption ratio below warning threshold.
- `warning`: consumption ratio at/above warning threshold and below exhausted threshold.
- `exhausted`: consumption ratio at/above exhausted threshold.
- `invalid`: reserved governed vocabulary for invalid measurements; this slice fail-closes on malformed input instead of emitting inferred invalid records.

## Fail-closed behavior
The runtime builder fails closed on:
- schema-invalid SLO, observability, or policy artifacts
- SLO/policy metric mismatch
- missing objective metric in observability payload
- incompatible measurement windows
- unsupported metric/operator semantics
- malformed thresholds or linkage fields

No objective is silently skipped.

## Authoritative integration seam
The artifact is attached at the same authoritative seam used for governed observability:
- `run_replay` in `spectrum_systems/modules/runtime/replay_engine.py`

When `slo_definition` is provided to replay, replay now emits:
- `replay_result.observability_metrics`
- `replay_result.error_budget_status`

This preserves direct trace/provenance linkage and keeps measurement semantics centralized in replay.

## Deliberate non-goals in this slice
- No alert dispatching
- No dashboard/UI updates
- No budget-based enforcement/gating behavior
- No multi-window burn-rate policy system
- No speculative metrics outside governed SLO/observability vocabulary
