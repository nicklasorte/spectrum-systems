# Dashboard Next Phase Serial 03 — Fix Handoff

## Purpose
Narrow follow-up prompt for only remaining blockers/high-leverage surgical fixes.

## Follow-up prompt
Implement only residual blockers (if any) discovered by full-suite execution after serial-03 merge:
1. Fix any failing dashboard certification-gate parity checks.
2. Fix any failing serial-03 panel fail-closed tests.
3. Fix any provenance completeness regressions for high-risk panels.
4. Do not add new panels or broaden scope.
5. Re-run dashboard build/tests and pytest; stop after publishing updated repair artifact.
