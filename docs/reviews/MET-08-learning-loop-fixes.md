# MET-08 — Fix Red-Team #1 Findings

## Prompt type
FIX

## Scope
Resolve every `must_fix` finding from MET-07. No `must_fix` remains open.

## Fixes

### MF-02: Override record needs explicit `next_recommended_input`
- **Finding**: `override_audit_log_record.json` lacked envelope-level
  `next_recommended_input`, leaving the unknown-state ambiguous.
- **Fix**: Added envelope-level `next_recommended_input` pointing at
  POL-CDE-OVERRIDE-AUDIT.
- **Files changed**: `artifacts/dashboard_metrics/override_audit_log_record.json`.
- **Tests added**: `apps/dashboard-3ls/__tests__/api/met-04-18-learning-loop.test.ts`
  asserts `override_count === 'unknown'`, `reason_codes` includes
  `override_history_missing`, and `next_recommended_input` is present.
- **Residual risk**: Until a canonical override log artifact exists, the
  record will continue to declare unknown by design.

### MF-03: Replace "approve" wording in policy candidate record
- **Finding**: Two suggested-policy-shape strings in
  `policy_candidate_signal_record.json` read as approval language.
- **Fix**: Replaced with "before adoption" and "policy review" wording,
  consistent with MET-allowed vocabulary (`recommendation`,
  `signal input`, `proposed`).
- **Files changed**: `artifacts/dashboard_metrics/policy_candidate_signal_record.json`.
- **Tests added**: Authority-vocabulary test in
  `apps/dashboard-3ls/__tests__/api/met-04-18-learning-loop.test.ts` scans MET-
  owned artifacts for banned tokens; preflight remains the binding gate.
- **Residual risk**: None for this finding. Future MET artifacts should reuse
  this vocabulary discipline.

## Verification
- All MET-04 through MET-06 artifacts re-scanned by hand and by the
  authority-vocabulary tests; no banned authority field/value or
  approval-shaped wording detected outside canonical-owner descriptions.
- Authority-shape preflight: green (see `outputs/authority_shape_preflight/`).
- 3LS authority preflight: green.

## Outcome
No `must_fix` remains open. MET-04 through MET-06 ship with envelope-level
`next_recommended_input` where applicable and only MET-allowed vocabulary in
recommendations.
