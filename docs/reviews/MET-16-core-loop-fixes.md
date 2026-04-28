# MET-16 — Fix Red-Team #2 Findings

## Prompt type
FIX

## Scope
Resolve every `must_fix` finding from MET-15. No `must_fix` remains open.

## Fixes

### MF2-01: Authority-shape leak in feedback-loop block name
- **Finding**: An early draft of `/api/intelligence/route.ts` named a
  feedback-loop block using an authority-shape token reserved for canonical
  owners (CDE).
- **Fix**: Renamed the API block to `feedback_loop` and the status string to
  `feedback_loop_status` before commit. The committed source no longer
  contains the original authority-shape token in any field name.
- **Files changed**: `apps/dashboard-3ls/app/api/intelligence/route.ts`.
- **Tests added**: API authority-vocabulary scan asserts the route source does
  not contain banned authority field names outside canonical owner contexts.
- **Residual risk**: None for this finding. Future API blocks must reuse
  MET-allowed vocabulary (`signal`, `recommendation`, `signal_input`).

### MF2-02: Override panel heading used authority-shape token
- **Finding**: Panel H heading originally read as MET claiming an authority
  it does not own.
- **Fix**: Renamed the panel heading to "Override / Unknowns (fail-closed)".
- **Files changed**: `apps/dashboard-3ls/app/page.tsx`.
- **Tests added**: Dashboard authority-vocabulary scan asserts the page source
  does not use banned authority words outside canonical-owner contexts.
- **Residual risk**: None for this finding.

## Verification
- API source re-scanned by hand and by tests; no banned authority field name
  outside canonical owner contexts.
- Dashboard UI re-scanned by hand and by tests; no banned heading tokens.
- Authority-shape preflight: green.
- 3LS authority preflight: green.

## Outcome
No `must_fix` remains open. SF2-01 (panel count) is tracked for MET-17/18; no
fold/remove is required by MET-15.
