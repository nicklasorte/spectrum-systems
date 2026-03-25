# Drift Detection (SRE-05)

## Scope
This slice compares a current governed `replay_result` artifact to an approved baseline `replay_result` artifact and emits `drift_detection_result`.

## Drift definition
Drift is measured only on approved bounded dimensions:
- `final_status_delta`
- `enforcement_action_delta`
- `consistency_mismatch_delta`
- `drift_detected_delta`
- `failure_reason_present_delta`

Each dimension is deterministic and computed as a binary delta (`0` or `1`).

## Baseline source
Baseline source is policy-governed via `baseline_gate_policy.required_baseline_source` and is emitted on the artifact (`approved_replay_baseline` or `approved_release_baseline`).

## Policy linkage
`build_drift_detection_result(...)` requires a schema-valid `baseline_gate_policy` and derives:
- threshold triggers
- reasons
- overall drift status (`no_drift`, `within_threshold`, `exceeds_threshold`)

## Fail-closed behavior
The module raises `DriftDetectionError` for:
- malformed current or baseline artifacts
- unsupported comparison target types
- malformed policy
- unknown/missing required metric surfaces

No permissive fallback or silent skipping is allowed.

## Integration boundary
This is wired into `run_replay(...)` when a baseline artifact is provided; output is attached to replay artifacts and consumed by baseline gating.

## Known limitations
- Current comparison target vocabulary is intentionally narrow (`replay_result` only).
- Dimensions are binary deltas; no multi-run aggregation is included in this slice.
