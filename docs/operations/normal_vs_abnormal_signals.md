# Normal vs Abnormal Signals

| Signal | Normal | Abnormal | Usually means | Inspect next |
| --- | --- | --- | --- | --- |
| capability_readiness_state | supervised/autonomous | constrained/unsafe | execution safety margin reduced | capability_readiness_record |
| drift_severity | none/warning | freeze/block | behavioral divergence from baseline | drift_detection_record |
| override_rate | <= 0.10 | > 0.10 | manual intervention pressure accumulating | override_governance_record |
| replay_match_rate | >= 0.98 | < 0.98 | replayability degradation | replay_execution_record |
| decision_quality_budget_status | healthy | warning/exhausted | decision budget nearing/exceeding limits | decision_quality_budget_status |
| promotion_consistency_status | consistent | inconsistent | promotion path no longer trustworthy | promotion_consistency_record |
| policy_conflict_count | 0 | >= 1 | policy graph unresolved | policy_conflict_record |
| stale_artifact_ratio | <= 0.05 | > 0.05 | stale carry-forward context risk | batch_handoff_bundle |
