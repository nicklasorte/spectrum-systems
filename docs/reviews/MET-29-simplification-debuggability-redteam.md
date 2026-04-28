# MET-29 — Red-Team #2: Simplification + Debuggability

## Prompt type
RED-TEAM

## Scope

Attacks against MET-19-33 simplicity and debuggability. The charter requires
that a new engineer answer what failed, why, where in the loop, source
evidence, and next recommended input in under 15 minutes.

## Attack surface

- Too many MET artifacts producing dashboard clutter.
- Duplicate metrics across MET-04-18 and MET-19-33.
- Dashboard panels that overflow operator attention budgets.
- Weak explanation packets that miss `next_recommended_input`.
- Artifacts that prevent no named failure or improve no measurable signal.
- 15-minute debug target failing because the index does not point to
  next_recommended_input.

## Findings

### F1 — must_fix — Compact sections must cap items
**finding:** Compact dashboard sections that render 20+ items defeat the
operator complexity budget.
**evidence:** `apps/dashboard-3ls/app/page.tsx` exposes
`MET_COMPACT_ITEM_MAX = 5` and every new section slices its data array.
The jest test
`apps/dashboard-3ls/__tests__/components/Met19_33Panels.test.tsx::compact sections do not render more than 5 items each`
asserts the cap.
**risk if unfixed:** Operator attention budget exceeded.

### F2 — must_fix — Debug index entries must point to next_recommended_input
**finding:** A debug entry without a next input fails the 15-minute target.
**evidence:** Each `explanation_entries[]` entry in
`debug_explanation_index_record.json` carries
`next_recommended_input` as a non-empty string. The contract test
`tests/metrics/test_met_19_33_contract_selection.py::test_debug_explanation_index_targets_under_15_minutes`
asserts it.
**risk if unfixed:** Operators stall after evidence lookup.

### F3 — must_fix — Each new artifact must justify itself by failure_prevented and signal_improved
**finding:** Every MET artifact must justify its existence.
**evidence:** All seven new artifacts carry top-level `failure_prevented`
and `signal_improved` strings. The contract test
`test_met_19_33_artifact_failure_prevented_and_signal_improved` enforces
non-empty strings.
**risk if unfixed:** Drift toward unjustified MET artifacts.

### F4 — must_fix — Duplicates between MET-04-18 and MET-19-33 are flagged
**finding:** MET-09 (`eval_materialization_path`) and MET-06
(`override_audit_log`) overlap MET-23 and MET-24 respectively.
**evidence:** MET-21 marks both as `fold_candidate` in the audit table and
the dependency index records the overlap. They are NOT removed in this PR
because canonical owners have not yet read the replacement records.
**risk if unfixed:** Operators see duplicate signals.

### F5 — should_fix — Dashboard panels stay compact
**finding:** Each new panel renders ≤5 top items with totals shown
separately.
**evidence:** New panels K, L, M, N, O each use `slice(0, MET_COMPACT_ITEM_MAX)`.
**risk if unfixed:** Section overflow.

### F6 — should_fix — Authority-neutral panel labels
**finding:** Section titles must use authority-neutral language.
**evidence:** Section titles use "Candidate Closure", "Debug Explanation",
"Trend / Frequency Honesty", "EVL Handoff Observations", "Artifact
Integrity". No banned heading variants appear.
**risk if unfixed:** UI authority leaks.

### F7 — observation — fold_candidate items must remain in place
**observation:** MET-19-33 does NOT remove `override_audit_log_record.json`
or `eval_materialization_path_record.json` in this PR; both remain wired
through the API and dashboard. The audit's fold recommendation stands as
advisory only.

## Classification summary

|severity|count|
|---|---|
|must_fix|4|
|should_fix|2|
|observation|1|

## Routing

All must_fix findings are addressed in
`MET-30-simplification-debuggability-fixes.md`.
