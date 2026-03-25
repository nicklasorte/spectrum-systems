# Observability Metrics (SRE-10)

## What is measured
This slice emits governed `observability_metrics` artifacts computed deterministically from existing governed artifacts produced by runtime/replay control paths.

## Authoritative integration seam
Primary integration is the **BAG replay result seam** (`run_replay` in `spectrum_systems/modules/runtime/replay_engine.py`).

Why this seam:
1. Replay already provides deterministic controlled comparison outputs.
2. Replay already binds decision/enforcement/drift and optional baseline-gate artifacts.
3. Replay artifacts are schema-governed and trace-linked, making measurement provenance explicit.

## Contract and example
- `contracts/schemas/observability_metrics.schema.json`
- `contracts/examples/observability_metrics.json`

## Deterministic computation rules
- Inputs must be governed artifacts from an allowed bounded set.
- Every source artifact is schema-validated before aggregation.
- Aggregation is pure arithmetic over bounded fields.
- Artifact identity is deterministic (`sha256` of canonical preimage).
- Output timestamp is derived from source artifacts (no runtime clock dependency).

## Currently emitted metrics
Always present:
- `total_runs`
- `replay_success_rate`

Conditionally present when source artifacts exist:
- `grounding_block_rate`
- `unsupported_claim_rate`
- `invalid_evidence_ref_rate`
- `drift_exceed_threshold_rate`
- `baseline_gate_block_rate`
- `regression_failure_rate`

## Trace and provenance linkage
The observability artifact includes:
- `trace_refs.trace_id`
- `run_ids`
- `source_artifact_ids`

Replay now embeds this artifact under `replay_result.observability_metrics` to preserve direct lineage.

## Fail-closed behavior
- Unknown input artifact types fail.
- Missing required linkage/metric fields fail.
- Inconsistent grounding counters fail.
- Unknown SLO metrics/operators fail.
- Schema-invalid output is rejected before return.

## Known limitations
- This slice computes measurement only.
- It does not implement alerting, paging, or error-budget burn policy enforcement.
- Metrics not derivable from currently provided governed source artifacts are intentionally not inferred.
