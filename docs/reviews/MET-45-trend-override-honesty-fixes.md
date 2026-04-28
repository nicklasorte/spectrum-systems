# MET-45 Trend and Override Honesty Fixes

## Prompt type
REVIEW

## must_fix closure

1. Added explicit `cases_needed` per insufficient pack in `trend_ready_case_pack_record.json`.
2. Added explicit absent-state warning plus unknown evidence count in `override_evidence_source_adapter_record.json`.

## files changed
- `artifacts/dashboard_metrics/trend_ready_case_pack_record.json`
- `artifacts/dashboard_metrics/override_evidence_source_adapter_record.json`
- `apps/dashboard-3ls/app/api/intelligence/route.ts`

## residual risk
Trend/frequency remain unknown until additional comparable cases are retrieved.

No must_fix items remain open.
