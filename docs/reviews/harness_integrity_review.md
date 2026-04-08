# BUNDLE-01-EXTENDED — Harness Integrity, Stress, Observability, and Reliability Review

## Scope
Primary type: `REVIEW`.

Authoritative generation command:
- `python scripts/run_harness_integrity_bundle.py --output-dir outputs/harness_bundle_review`

Verification command (fail-closed if review exists and outputs missing/empty):
- `python scripts/run_harness_integrity_bundle.py --verify-only --output-dir outputs/harness_bundle_review`

## Generated artifacts (authoritative)
Directory:
- `outputs/harness_bundle_review/`

Required reports:
1. `harness_integrity_report.json`
2. `transition_consistency_report.json`
3. `state_consistency_report.json`
4. `policy_path_consistency_report.json`
5. `failure_injection_report.json`
6. `harness_observability_metrics.json`
7. `trace_completeness_report.json`
8. `drift_detection_report.json`
9. `error_budget_status.json`
10. `replay_integrity_report.json`

Machine-consumable indexes:
- `artifact_index.json`
- `harness_bundle_index.json`

## Top findings (from generated `harness_bundle_index.json`)
1. `integrity:permission_decision_record_presence` — **blocking** (affected subsystem: integrity)
2. `integrity:checkpoint_linkage_presence` — **blocking** (affected subsystem: integrity)
3. `transition:mismatch_detected` — **warning** (affected subsystem: cross_system_transitions)

Current generated summary fields (from `harness_bundle_index.json`):
- `readiness_score`: 40
- `blocking_findings_count`: 2
- `warning_findings_count`: 1
- `ready_for_bundle_02`: false

## Evidence model
This document is informational. The JSON artifacts above are the only authoritative evidence for downstream fix bundles.
