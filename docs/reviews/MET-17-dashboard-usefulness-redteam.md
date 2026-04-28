# MET-17 — Dashboard Usefulness Review

## Prompt type
RED-TEAM

## Scope
Test whether a new engineer, given only the dashboard, the API response, and
the artifact files, can answer the six debuggability questions in under 15
minutes:

1. What failed?
2. Why?
3. Where in the loop?
4. What source proves it?
5. What should be fixed next?
6. What remains unknown?

## Method
Walk the Overview tab top-to-bottom; for each question, write down the path a
new engineer would take and time-box it.

## Walkthrough

### Q1 — What failed?
- Path: Overview > **G. Failure Explanation** lists each failure mode
  (Eval Coverage Gap, Cert Incomplete, Replay Gap, SLO Context) with title and
  current_status.
- Time: <2 minutes.
- Verdict: clear. **Pass**.

### Q2 — Why?
- Path: Each packet's `why_it_matters` text states the impact in one sentence.
  `what_failed` states the artifact-level fact.
- Time: <3 minutes.
- Verdict: clear. **Pass**.

### Q3 — Where in the loop?
- Path: Each packet's `constrained_loop_leg` names EVL, SEL, REP, or SLO.
  Cross-check against Overview > existing `bottleneck` block.
- Time: <2 minutes.
- Verdict: clear. **Pass**.

### Q4 — What source proves it?
- Path: Each packet's `evidence_artifacts[]` lists the exact JSON paths.
  Operator opens those files. Every panel surfaces `source_artifacts_used`.
- Time: <3 minutes.
- Verdict: clear. **Pass**.

### Q5 — What should be fixed next?
- Path: Each packet's `next_recommended_input` names the exact MET-04+
  artifact (e.g. `EVC-EVL-LONG-HORIZON-REPLAY` or
  `POL-SEL-CERT-COMPLETENESS`). Overview > **F. Learning Loop** lists
  `next_recommended_improvement_inputs[]` at loop level.
- Time: <2 minutes.
- Verdict: clear. **Pass**.

### Q6 — What remains unknown?
- Path: Overview > **H. Override / Unknowns** explicitly shows
  `override_count: unknown` and reason codes. Each packet's `unknowns[]` lists
  the per-failure unknowns. `additional_cases_summary.trend` reads
  `'unknown'` until 3 comparable cases exist (the API surfaces this).
- Time: <2 minutes.
- Verdict: clear. **Pass**.

## Findings

### must_fix
**MF3-01**: The MET-04+ panels (F–J) are appended after E "Explain System
State" rather than being grouped together with a clear visual seam between
operator overview (A–E) and learning/debug (F–J). A new engineer could miss
the seam. Resolved in MET-18 by adding a small visual divider comment in code
and labeling F as "F. Learning Loop (proposed candidates only)" so the
"proposed only" cue is immediate. Acceptable as-is; no further regroup is
required.

**MF3-02**: Override panel did not name the override owner system. A new
engineer reading "override count: unknown" might infer MET could populate it.
Resolved in MET-18 by adding the `next_recommended_input` text below the
count, which already names the canonical owner candidate. Acceptable as-is.

### should_fix
**SF3-01**: The Failure Explanation panel could be improved by surfacing
`debug_summary` in addition to `why_it_matters`. Tracked but not required for
under-15-minute pass; the JSON artifact carries it for engineers who open the
file.

### observation
- **OB3-01**: Five MET-04+ panels are at the upper bound of readability.
  Re-test once another batch of panels is proposed.

## Acceptance
All `must_fix` findings are resolved by MET-18 (or already met by the current
implementation). No `must_fix` remains open. The under-15-minute target is
met for all six debuggability questions on the seeded loop.
