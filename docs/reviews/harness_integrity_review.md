# BUNDLE-01-EXTENDED — Harness Integrity, Stress, Observability, and Reliability Review

## Scope
Primary type: `REVIEW`.

Authoritative generation command:
- `python scripts/run_harness_integrity_bundle.py --output-dir outputs/harness_bundle_review`

Verification command (fail-closed if review exists and outputs missing/empty):
- `python scripts/run_harness_integrity_bundle.py --verify-only --output-dir outputs/harness_bundle_review`

## Generated artifacts (authoritative)
All required outputs are generated as JSON files under:
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

Index:
- `artifact_index.json`

## Backing logic
The generated artifacts are computed from exercised PQX, prompt queue, orchestration, replay, drift, observability, and governed failure-injection seams in `scripts/run_harness_integrity_bundle.py`.

This review document is informational only; the generated JSON artifacts are the runtime source of truth.
