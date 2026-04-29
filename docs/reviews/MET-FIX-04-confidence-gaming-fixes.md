# MET-FIX-04 Confidence / Gaming Fixes

## Prompt type
REVIEW

## must_fix closure

### finding 1
High confidence must require minimum 3 evidence_refs.

### fix 1
`signal_confidence_record.json` declares
`minimum_evidence_count_for_high_confidence: 3` and flags
`high_confidence_thin_evidence` for any signal with `confidence_level:
high_claimed` and fewer than 3 evidence refs.

### finding 2
Misleading-signal detection must flag stale signals and high-confidence
thin-evidence cases.

### fix 2
`misleading_signal_detection_record.json` carries flagged observations:
- `high_confidence_thin_evidence` for SIG-GOV-FALLBACK-PRESSURE
- `stale_signal_rendered_as_current` for POL-GOV-FALLBACK-REDUCTION

### finding 3
API blocks must degrade to unknown — never substitute 0.

### fix 3
`metBlock` builder in `app/api/intelligence/route.ts` returns
`data_source: 'unknown'` and `status: 'unknown'` plus a missing-artifact
warning when the artifact is absent. No 0 substitution.

### files changed
- `artifacts/dashboard_metrics/signal_confidence_record.json`
- `artifacts/dashboard_metrics/recommendation_accuracy_record.json`
- `artifacts/dashboard_metrics/calibration_drift_record.json`
- `artifacts/dashboard_metrics/metric_gaming_detection_record.json`
- `artifacts/dashboard_metrics/misleading_signal_detection_record.json`
- `artifacts/dashboard_metrics/signal_integrity_check_record.json`
- `apps/dashboard-3ls/app/api/intelligence/route.ts`

### tests added
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_confidence_warns_with_thin_evidence`
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_anti_gaming_flags_misleading_green_states`
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_signal_integrity_aggregate`
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_calibration_remains_unknown_until_enough_outcomes`

### residual risk
Calibration drift state stays insufficient_cases until at least 5 paired
outcomes per bucket exist. Anti-gaming surface relies on canonical owners
producing after-state evidence to compute outcomes.

No must_fix items remain open.
