# Service Level Objectives (SRE-08)

## Service under measurement
This slice defines governed SLOs for the **Spectrum runtime/replay control surface** (control-loop + replay outputs used for deterministic reliability assessment).

## Artifact contract
SLO definitions are published as `service_level_objective` artifacts under:
- `contracts/schemas/service_level_objective.schema.json`
- `contracts/examples/service_level_objective.json`

## Governed metric vocabulary
SLO objectives are bounded to currently-computable metrics only:
- `replay_success_rate`
- `grounding_block_rate`
- `unsupported_claim_rate`
- `invalid_evidence_ref_rate`
- `drift_exceed_threshold_rate`
- `baseline_gate_block_rate`
- `regression_failure_rate`

Unknown metric names are rejected fail-closed.

## SLO semantics
Each objective defines:
- `metric_name`
- `target_operator` (`gte`, `lte`, `eq`)
- `target_value` (`0.0`–`1.0`)
- `severity_on_breach` (`warn`, `block`)

Breach evaluation is deterministic and performed directly against computed metrics.

## Fail-closed rules
- Malformed SLO definitions are rejected.
- Unknown objective operators are rejected.
- If an SLO references a metric that is not computable from provided governed source artifacts, evaluation fails closed.

## Deliberate non-goals in this slice
- No alert dispatching
- No dashboard rendering
- No error-budget burn enforcement actions
- No runtime gating behavior changes
