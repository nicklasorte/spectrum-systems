# MET-15 — Red-Team #2: Core Loop Strength Review

## Prompt type
RED-TEAM

## Scope
Review every artifact, every API field, and every UI panel introduced in
MET-04 through MET-14. Test whether each item strengthens the core loop
`AEX → PQX → EVL → TPA → CDE → SEL` (with `REP/LIN/OBS/SLO` overlays) or
helps debug failures.

## Method
For each item: ask whether removing it would weaken the loop. If not,
recommend fold/remove. Then pass the same set through the authority-boundary
check, freshness check, and panel-bloat check.

## Findings

### Does each artifact strengthen execution → eval → control → `enforcement_signal`?
Yes:
- `failure_feedback_record` and `eval_candidate_record` strengthen
  EVL by routing failure observations to proposed candidates with sources.
- `policy_candidate_signal_record` strengthens TPA / CDE / SEL by routing
  authority-boundary observations to the right canonical owners.
- `eval_materialization_path_record` directly attacks the EVL bottleneck by
  documenting the path from MET candidate to EVL artifact.
- `replay_lineage_hardening_record` and `fallback_reduction_plan_record`
  strengthen REP / LIN and the high-leverage non-loop systems.
- `failure_explanation_packets` strengthens debuggability across all legs.
- `override_audit_log_record` keeps the unknown-state explicit so the loop
  cannot quietly assume zero overrides.
- `sel_compliance_signal_input_record` strengthens SEL posture clarity.
- `dashboard_cases/*` strengthens triangulation by adding 3 comparable cases.

### Does each artifact help debug failures?
Yes. Each MET-04+ artifact carries `source_artifacts_used` and either an
explicit `next_recommended_input` or a `debug_summary` that points the reader
to the next artifact and the next action.

### Did we add complexity without leverage?
**should_fix SF2-01** raised: the dashboard now has four MET-04+ panels (F, G,
H, I, J — five). Five compact sections is at the upper bound of the prompt's
"compact, not giant tables" guideline. Recommendation: keep all five for
MET-04-18 because each maps to a distinct named MET-04+ artifact and the
prompt explicitly lists Learning Loop, Failure Explanation, Override/Unknowns,
Fallback Reduction, and Replay+Lineage Hardening as required UI sections.
No `must_fix` raised.

### Are any candidates stale or unowned?
No. Every candidate (`EVC-*`, `POL-*`) carries `owner_recommendation` (EVL,
SEL, TPA, GOV, CDE) and `status: "proposed"`. None are stale because the
candidates are seeded as new in this PR.

### Are unknown states visible?
Yes. `override_count: "unknown"`, `additional_cases_summary.trend: "unknown"`
(when fewer than 3 comparable cases), every `*_count` field that the artifact
does not populate degrades to `'unknown'` in `/api/intelligence`, never 0.

### Are authority boundaries preserved?
**must_fix MF2-01** raised then resolved: an early draft of the API route
named a feedback-loop block using an authority-shape token reserved for
canonical owners (CDE). Resolved by renaming the block to `feedback_loop`
and the status to `feedback_loop_status` before commit. Re-scan: clean.

**must_fix MF2-02** raised then resolved: the dashboard panel "H. Override /
Unknowns" originally used a heading containing an authority-shape token.
Renamed to "Override / Unknowns (fail-closed)" to keep MET vocabulary
discipline. Re-scan: clean.

### Are there too many panels / artifacts?
**observation OB2-01**: With F–J added, the Overview now has nine panels.
This is at the upper end of operator readability. MET-17 will explicitly
test this against the under-15-minute usefulness target. No `must_fix`
because the prompt requires those sections. If MET-17 finds the
overview-tab unreadable, MET-18 must fold or move sections.

## Findings classification

| ID    | Class       | Title                                                        | Status  |
|-------|-------------|--------------------------------------------------------------|---------|
| MF2-01| must_fix    | Authority-shape leak in feedback-loop block name             | fixed   |
| MF2-02| must_fix    | Override panel heading used authority-shape token            | fixed   |
| SF2-01| should_fix  | Five MET-04+ panels approach upper bound for readability     | tracked |
| OB2-01| observation | Overview now has nine panels — re-test in MET-17             | kept    |

## Acceptance
All `must_fix` findings are resolved by MET-16. No `must_fix` remains open.
