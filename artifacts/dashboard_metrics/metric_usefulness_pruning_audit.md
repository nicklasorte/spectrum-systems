# MET Metric Usefulness Pruning Audit (MET-FULL-ROADMAP)

## Owner
MET (non-owning measurement capability). MET does not delete or fold artifacts;
this audit emits observations only.

## Failure Prevented
Useful provenance and debug surfaces being removed in the name of "simplification"
without proof of replacement coverage.

## Signal Improved
Each MET-owned artifact and dashboard panel is checked against the canonical
fold rule:

> An artifact or dashboard panel may be folded only if its replacement covers
> the same `failure_prevented`, the same `signal_improved`, the same upstream
> artifacts, the same downstream consumers, and the same debug questions.

## Audit Method
Each candidate is scored against:
- `same_failure_prevented`
- `same_signal_improved`
- `upstream_artifacts_covered`
- `downstream_consumers_covered`
- `debug_questions_covered`

Anything missing one or more flags is reported as `not_ready_observation`.

Source: `artifacts/dashboard_metrics/fold_candidate_proof_check_record.json`.

## Audit Results (observation only)

| Candidate                                | Replacement                                    | Same FP | Same SI | Upstream | Downstream | Debug | Observation              |
| ---------------------------------------- | ---------------------------------------------- | :-----: | :-----: | :------: | :--------: | :---: | ------------------------ |
| FOLD-EVL-HANDOFF-TO-OWNER-READ           | owner_read_observation_ledger_record           |   ✓    |   ✓    |    ✓    |     ✗     |   ✓  | not_ready_observation    |
| FOLD-EVAL-MATERIALIZATION-TO-MAPPER      | materialization_observation_mapper_record      |   ✓    |   ✓    |    ✓    |     ✓     |   ✓  | fold_ready_observation   |

## What Is Kept (and why)
- `candidate_closure_ledger_record.json` — sole tracker of stale/open candidate state.
- `owner_read_observation_ledger_record.json` — sole tracker of owner read observations.
- `materialization_observation_mapper_record.json` — sole mapper of materialization observations.
- `outcome_attribution_record.json` — sole tracker of before/after deltas.
- `recommendation_accuracy_record.json` and `calibration_drift_record.json` — required for
  confidence/calibration honesty.
- `signal_integrity_check_record.json`, `metric_gaming_detection_record.json`,
  `misleading_signal_detection_record.json` — required for anti-gaming.
- `operator_debuggability_drill_record.json`, `time_to_explain_record.json`,
  `debug_readiness_sla_record.json` — required for the six-question debug path.

## What May Eventually Fold (with proof)
- `evl_handoff_observation_tracker_record.json` may fold into
  `owner_read_observation_ledger_record.json` once downstream consumer coverage
  is proven (test added that asserts the same handoff signal surface in API +
  dashboard).

## Constraints
- No fold is performed in this PR.
- MET is non-owning. Any fold action belongs to canonical owners through a
  governed PR.
- No fold removes useful provenance. Source artifacts remain reachable until
  every flag is verified.
