# MET-FULL-ROADMAP Final Review

## Prompt type
REVIEW

## MET registry entry summary
- Registered in `docs/architecture/system_registry.md` as `active, non-owning`.
- Authority: `NONE`.
- Forbidden ownership tokens: `decision_ownership`, `approval_ownership`,
  `enforcement_ownership`, `certification_ownership`, `promotion_ownership`,
  `execution_ownership`, `admission_ownership`.
- Invariant: if MET produces an authority outcome, block.
- Upstream Dependencies: EVL, LIN, REP, OBS, SLO, TPA, CDE, SEL.
- Downstream Consumers: AEX, PQX, EVL, TPA, CDE, SEL, GOV, dashboard-3ls.
- Listed in System Map and lower System Definitions section with
  `must_not_do` covering all forbidden ownership tokens.

## What was built

### New MET artifacts under `artifacts/dashboard_metrics/`
- `stale_candidate_pressure_record.json`
- `metric_usefulness_pruning_audit.md`
- `outcome_attribution_record.json`
- `failure_reduction_signal_record.json`
- `recommendation_accuracy_record.json`
- `calibration_drift_record.json`
- `signal_confidence_record.json`
- `cross_run_consistency_record.json`
- `divergence_detection_record.json`
- `met_error_budget_observation_record.json`
- `met_freeze_recommendation_signal_record.json`
- `next_best_slice_recommendation_record.json`
- `pqx_candidate_action_bundle_record.json`
- `counterfactual_reconstruction_record.json`
- `earlier_intervention_signal_record.json`
- `recurring_failure_cluster_record.json`
- `recurrence_severity_signal_record.json`
- `time_to_explain_record.json`
- `debug_readiness_sla_record.json`
- `metric_gaming_detection_record.json`
- `misleading_signal_detection_record.json`
- `signal_integrity_check_record.json`

### API
`apps/dashboard-3ls/app/api/intelligence/route.ts` exposes:
- `met_registry_status`, `met_cockpit`, `top_next_inputs`, `owner_handoff`,
  `stale_candidate_pressure`, `trend_readiness`, `override_evidence`,
  `fold_safety`, `outcome_attribution`, `failure_reduction_signal`,
  `recommendation_accuracy`, `calibration_drift`, `signal_confidence`,
  `cross_run_consistency`, `divergence_detection`, `error_budget_observation`,
  `freeze_recommendation_signal`, `next_best_slice`,
  `pqx_candidate_action_bundle`, `counterfactuals`,
  `earlier_intervention_signal`, `recurring_failures`,
  `recurrence_severity_signal`, `debug_readiness`, `time_to_explain`,
  `metric_gaming_detection`, `misleading_signal_detection`,
  `signal_integrity`.

Every block carries `data_source`, `source_artifacts_used`, `warnings`, and
`status`. Missing artifacts degrade to `unknown` — never to 0.

### Dashboard
`apps/dashboard-3ls/app/page.tsx` adds two new compact panels in the
overview tab:
- `A2. MET Cockpit (non-owning observations)` — answers: trust, weakest
  loop leg, top 3 next inputs, owner handoff queue, stale candidate
  pressure, trend readiness, debug readiness, artifact integrity, outcome
  attribution, confidence/calibration, recurrence, anti-gaming.
- `A3. MET Outcome / Calibration / Integrity` — outcome attribution,
  calibration drift, recurring failures, signal integrity (max 5 rendered
  items per section).

No action buttons in MET-owned UI (no `Execute`, `\`approve_action\``,
`\`promote_action\``, `\`admit_action\``, or `\`enforce_action\`` labels).
Authority is explicitly rendered as `NONE`.

### Tests
- `tests/metrics/test_met_full_roadmap_contract_selection.py`
- `apps/dashboard-3ls/__tests__/api/met-full-roadmap-intelligence.test.ts`

## What was simplified
- Common MET block construction moved to a `metBlock` helper in the API
  route, replacing per-artifact ternary blocks for the new surfaces while
  preserving fail-closed behaviour.
- `metric_usefulness_pruning_audit.md` enumerates fold safety per
  candidate; only fold-ready candidates are advisory and none are folded
  in this PR.

## Failures prevented
- Undetected bottlenecks (cockpit shows weakest_loop_leg).
- Unclear failure causes (counterfactual reconstruction + debug SLA).
- Stale candidates (stale_candidate_pressure + closure ledger).
- Fake trends (3-case threshold preserved).
- Unverified improvements (outcome attribution requires before/after).
- Overconfident recommendations (signal confidence flags thin evidence).
- Recurring failures (cluster threshold = 3).
- Metric gaming (gaming + misleading-signal + integrity records).

## Signals improved
- Debuggability (time-to-explain + debug readiness SLA).
- Bottleneck clarity (cockpit weakest_loop_leg).
- Closure visibility (stale_candidate_pressure).
- Outcome attribution (outcome_attribution_record).
- Recommendation calibration (calibration_drift_record).
- Signal integrity (signal_integrity_check_record).

## Remaining unknowns
- After-state evidence for the long-horizon replay slice.
- GOV-side fallback registry retrieval.
- CDE override audit log evidence intake.
- Calibration buckets stay insufficient_cases until at least 5 paired
  outcomes per bucket exist.
- Recurrence clusters stay insufficient_cases until 3+ comparable cases
  per shape.

## Outcome attribution state
All current entries are `insufficient_evidence` or `unknown`. No fake
observed claims. MET surfaces the gap rather than declaring improvement.

## Confidence / calibration state
Calibration drift state is `unknown` or `insufficient_cases` for every
bucket. One signal (`SIG-GOV-FALLBACK-PRESSURE`) is flagged
`high_confidence_thin_evidence`.

## Signal integrity state
Aggregate `overall_integrity_state: warn`. Two flagged misleading-signal
observations (high_confidence_thin_evidence and stale_signal_rendered_as_current).
No metric gaming flags. No unknown-to-zero substitutions.

## Red-team findings / fixes
- MET-RT-01 → MET-FIX-01: registry authority. No must_fix open.
- MET-RT-02 → MET-FIX-02: dashboard clarity. No must_fix open.
- MET-RT-03 → MET-FIX-03: trend / outcome honesty. No must_fix open.
- MET-RT-04 → MET-FIX-04: confidence / gaming. No must_fix open.
- MET-RT-05 → MET-FIX-05: debuggability. No must_fix open.

## Tests run
See validation log (Part 20) for full output. Anchor tests:
- `pytest tests/metrics/test_met_full_roadmap_contract_selection.py`
- `pytest tests/metrics/test_met_34_47_contract_selection.py`
- `pytest tests/test_authority_shape_preflight.py`
- `pytest tests/governance/test_3ls_authority_preflight.py`
- `npm run test` (dashboard suite)

## Authority preflight result
Authority-shape preflight remains the canonical static gate. MET-owned
artifacts use observation/recommendation/signal vocabulary; the new
artifact set carries no banned authority tokens.

## Contract preflight result
Contract preflight wrapper anchors are unchanged; this PR adds
`tests/metrics/test_met_full_roadmap_contract_selection.py` as a selection
target.

## Remaining next steps
- Pair outcome attribution entries with after-state evidence as canonical
  owners produce it.
- Author DRILL-GOV-FALLBACK-001 to raise GOV debug readiness from unknown
  to partial.
- Capture a paired second run for cross_run_consistency to move
  divergence detection from `unknown` to `false`.
- Once 5 paired outcomes per bucket exist, calibration drift moves from
  insufficient_cases to a bucket-specific state.

## Acceptance criteria check
- MET registered as active non-owning system: yes.
- MET Cockpit integrated into dashboard overview tab: yes.
- Outcome attribution exists: yes.
- Confidence / calibration exists: yes.
- Cross-run consistency exists: yes.
- Error budget observation exists: yes.
- Action bundle candidate exists: yes (proposed only).
- Counterfactual reconstruction exists: yes.
- Recurrence detection exists: yes (insufficient_cases when below threshold).
- Debug SLA exists: yes.
- Anti-gaming / signal integrity exists: yes.
- Every artifact prevents a failure or improves a signal: yes.
- All red-team must_fix findings fixed: yes.
- No fake PASS / fake green / fake trend / fake owner acceptance: confirmed.
- No authority creep: MET authority remains NONE.
- Dashboard build / tests pass: see Part 20.
- Authority preflight passes: see Part 20.
- Contract preflight passes: see Part 20.
- One PR only: this PR.
