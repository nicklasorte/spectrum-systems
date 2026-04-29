# MET-FIX-05 Debuggability Fixes

## Prompt type
REVIEW

## must_fix closure

### finding 1
Every drill item must answer the canonical six questions.

### fix 1
`operator_debuggability_drill_record.json` is unchanged in this PR but the
new `time_to_explain_record.json` and `debug_readiness_sla_record.json` cite
the canonical six questions:
- what_failed
- why
- where_in_loop
- source_evidence
- next_recommended_input
- what_remains_unknown

### finding 2
Counterfactual entries must cite evidence; unknown stays unknown.

### fix 2
`counterfactual_reconstruction_record.json` includes a CF-CDE-OVERRIDE-AUDIT
entry where `reconstruction_state: unknown` until override evidence is
captured. Tests verify `evidence_refs` are present where reconstruction is
not unknown.

### finding 3
Debug readiness SLA states must be one of sufficient / partial / insufficient
/ unknown.

### fix 3
`debug_readiness_sla_record.json` declares
`readiness_states_allowed: [sufficient, partial, insufficient, unknown]` and
all current entries fall in `partial` or `unknown`.

### files changed
- `artifacts/dashboard_metrics/time_to_explain_record.json`
- `artifacts/dashboard_metrics/debug_readiness_sla_record.json`
- `artifacts/dashboard_metrics/counterfactual_reconstruction_record.json`
- `artifacts/dashboard_metrics/earlier_intervention_signal_record.json`

### tests added
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_artifacts_have_required_envelope`
  enforces envelope on debug readiness records.
- `apps/dashboard-3ls/__tests__/api/met-full-roadmap-intelligence.test.ts`
  asserts dashboard cockpit surfaces debug_readiness state.

### residual risk
GOV-fallback drill is not yet authored; debug readiness for that path stays
unknown. MET surfaces the gap rather than hiding it.

No must_fix items remain open.
