# MET-18 — Fix Dashboard Usefulness Findings

## Prompt type
FIX

## Scope
Resolve every `must_fix` finding from MET-17. No `must_fix` remains open.

## Fixes

### MF3-01: Visual seam between operator overview and learning/debug panels
- **Finding**: A new engineer could miss that F–J are MET-04+ panels because
  they appear after E without a visible seam.
- **Fix**: Each new panel title carries an explicit cue: "(proposed
  candidates only)", "(debug under 15 minutes)", "(fail-closed)",
  "(high-leverage rows only)". The cue is the seam. Override panel also
  shows the `next_recommended_input` text immediately below the count, which
  reads as the next-action signal a new engineer needs.
- **Files changed**: `apps/dashboard-3ls/app/page.tsx`.
- **Tests added**: `apps/dashboard-3ls/__tests__/api/met-04-18-dashboard.test.tsx`
  asserts the new panels render with their data-testid attributes and that
  no banned authority headings appear.
- **Residual risk**: None for this finding.

### MF3-02: Override panel did not name canonical owner candidate
- **Finding**: "override count: unknown" without a `next_recommended_input`
  string could read as MET being the missing populator.
- **Fix**: Override panel renders `next_recommended_input` text, which names
  POL-CDE-OVERRIDE-AUDIT as the candidate signal addressed to CDE/GOV.
- **Files changed**: `apps/dashboard-3ls/app/page.tsx`,
  `artifacts/dashboard_metrics/override_audit_log_record.json`.
- **Tests added**: API test asserts `override_audit.next_recommended_input`
  is non-empty when artifact is present.
- **Residual risk**: None for this finding. The unknown state remains
  visible by design until a canonical override log artifact exists.

## Verification
- Manual walkthrough of Overview tab confirms all six debuggability
  questions remain answerable in under 15 minutes.
- Authority-vocabulary tests: green.
- Dashboard build / tests: green (see MET-04-18 final integration review).

## Outcome
No `must_fix` remains open. SF3-01 (debug summary in panel) is tracked for a
future MET phase; the JSON artifact already carries `debug_summary` for
engineers who open the file.
