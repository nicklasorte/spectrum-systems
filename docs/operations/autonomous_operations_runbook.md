# Autonomous Operations Runbook

## 1) Scope of unattended operation

### Allowed unattended roadmap types
- Execution type: deterministic `BUILD` and `WIRE` slices that only consume governed contract artifacts and pass preflight gates.
- Validation type: bounded `VALIDATE` slices with replayable fixtures and no external/network dependency.
- Not unattended: `PLAN` creation, checkpoint release decisions, and any action requiring policy exception approval.

### Artifact families in scope
- Roadmap/control artifacts (`system_roadmap`, `roadmap_multi_batch_run_result`, `next_cycle_decision`, `next_cycle_input_bundle`).
- Trust and readiness artifacts (`capability_readiness_record`, `trust_posture_snapshot`, `decision_quality_budget_status`).
- Promotion/policy/override artifacts (`judgment_promotion_gate_record`, `promotion_consistency_record`, `policy_*`, `override_governance_record`).
- Handoff/operator artifacts (`build_summary`, `batch_handoff_bundle`, `operations_monitoring_contract`).

### Promotion-sensitive flows
- Any flow with `promotion_gate_state != pass`.
- Any flow with `promotion_consistency_status != consistent`.
- Any flow with certification artifacts on the critical path.

### Flows requiring human review
- Any `freeze`/`block` severity in monitoring signals.
- Any unresolved policy conflict.
- Any repeated freeze/block on the same subsystem across two consecutive batches.
- Any override accumulation over threshold.

## 2) Normal operating envelope

| Signal | Normal envelope |
| --- | --- |
| `capability_readiness_state` | `supervised` or `autonomous` |
| `trust_posture_snapshot.overall_trust_state` | `healthy` or `watch` |
| `drift_severity` | `none` or `warning` |
| `override_rate` | `<= 0.10` |
| `replay_match_rate` | `>= 0.98` |
| `budget_status` | `healthy` |
| `promotion_gate_state` | `pass` |

## 3) Intervention triggers
Human intervention is required when **any** condition is true:
1. Same subsystem enters `freeze` or `block` in 2 consecutive governed batches.
2. `drift_severity = block` on critical path artifacts.
3. `policy_conflict_count > 0` and conflict unresolved by end of batch.
4. `override_rate > 0.10` in current batch.
5. Promotion-path certification failure (`promotion_consistency_status = inconsistent` or gate not `pass`).

## 4) Deterministic triage procedure
Inspect artifacts in this strict order:
1. `trust_posture_snapshot`
2. `drift_detection_record`
3. `capability_readiness_record`
4. `batch_handoff_bundle`
5. `control_decision` + `decision_proof`
6. promotion/policy/override artifacts (`judgment_promotion_gate_record`, `policy_conflict_record`, `override_governance_record`)

Do not skip steps; do not branch order.

## 5) Safe halt / resume rules

### Normal halt
A halt is normal when caused by governed stop conditions (max batch bound reached, fail-closed guard triggered, or required human review gate).

### Resume allowed when
- all blocking artifacts are resolved,
- monitoring severity returns to `normal` or `warning`, and
- replay parity checks remain deterministic.

### Regenerate roadmap when
- stop cause invalidates downstream batch assumptions,
- policy conflicts altered allowed execution path, or
- promotion constraints changed.

### Invalidate prior handoff when
- source `trace_id` lineage is broken,
- any required carry-forward artifact is stale/absent,
- decision proof is superseded by remediated control decision.

## 6) Audit checklist (minimum artifact set)
To answer "what ran, why continued/stopped, what changed, what policy activated, and whether promotion was valid", collect:
- `roadmap_multi_batch_run_result`
- `build_summary`
- `batch_handoff_bundle`
- `next_cycle_decision` + `decision_proof_record`
- `trust_posture_snapshot`
- `operations_monitoring_contract`
- `promotion_consistency_record` + `judgment_promotion_gate_record`
- `policy_activation_record` + `policy_conflict_record`
- `override_governance_record`
