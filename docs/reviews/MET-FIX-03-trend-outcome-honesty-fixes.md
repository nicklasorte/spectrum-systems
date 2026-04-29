# MET-FIX-03 Trend / Outcome Honesty Fixes

## Prompt type
REVIEW

## must_fix closure

### finding 1
Trend stays unknown until 3 comparable cases.

### fix 1
Existing `trend_frequency_honesty_gate_record` and
`comparable_case_qualification_gate_record` already require min_case_count = 3
plus same-failure_shape / affected_systems / evaluated_fields / source_type
comparability rules; new `recurring_failure_cluster_record` carries
`minimum_comparable_cases_for_recurrence: 3` and exposes `cases_needed` when
below threshold.

### finding 2
Outcome status must be one of insufficient_evidence / partial / observed /
unknown; `observed` requires non-empty before AND after evidence_refs.

### fix 2
`outcome_attribution_record.json` is authored with all current entries at
`insufficient_evidence` or `unknown`. Tests in
`tests/metrics/test_met_full_roadmap_contract_selection.py::test_outcome_attribution_requires_before_after_for_observed_status`
assert that observed entries carry both before and after `evidence_refs`.

### finding 3
Recurrence stays insufficient_cases until threshold met.

### fix 3
`recurring_failure_cluster_record.json` clusters today are
`insufficient_cases` with `cases_needed > 0`. Tests assert this invariant.

### files changed
- `artifacts/dashboard_metrics/outcome_attribution_record.json`
- `artifacts/dashboard_metrics/failure_reduction_signal_record.json`
- `artifacts/dashboard_metrics/recurring_failure_cluster_record.json`
- `artifacts/dashboard_metrics/recurrence_severity_signal_record.json`

### tests added
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_outcome_attribution_requires_before_after_for_observed_status`
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_recurrence_requires_multiple_comparable_cases`
- `apps/dashboard-3ls/__tests__/api/met-full-roadmap-intelligence.test.ts`
  parallel checks.

### residual risk
Outcome attribution remains thin until canonical owners produce after-state
evidence. MET keeps surfacing unknown / insufficient_evidence rather than
fake observed.

No must_fix items remain open.
