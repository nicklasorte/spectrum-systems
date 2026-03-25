# Baseline Gating (SRE-06)

## Scope
`baseline_gating.py` consumes `drift_detection_result` and a governed `baseline_gate_policy`, then emits `baseline_gate_decision`.

## Deterministic mapping
Status mapping is fixed and fail-closed:
- `invalid_comparison` -> `block` / `block_promotion`
- `exceeds_threshold` -> `block` / `block_promotion`
- `within_threshold` + warn thresholds -> `warn` / `flag`
- `no_drift` -> `pass` / `allow`

## Enforcement boundary choice
This slice enforces at replay/runtime control boundary (`run_replay(...)`):
- decision `allow` or `flag` -> replay result returned
- decision `block_promotion` -> `ReplayEngineError(BASELINE_GATE_BLOCKED...)` raised

This ensures the result is not only reported but actually blocks downstream promotion paths.

## Policy linkage
Policy is loaded from:
- `data/policy/baseline_gate_policy.json` (canonical default)

Policy controls:
- supported comparison target types
- supported dimensions
- per-dimension warn/block thresholds
- required baseline source
- invalid comparison action

## Trace/provenance linkage
Decision artifacts carry explicit `trace_id`, `run_id`, `drift_result_id`, `policy_id`, and `baseline_id` to preserve cross-artifact lineage.

## Known limitations
- Policy currently supports one target type (`replay_result`).
- Decision artifact is attached to replay output only when baseline comparison is explicitly requested.
