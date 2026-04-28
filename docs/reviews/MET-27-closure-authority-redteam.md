# MET-27 — Red-Team #1: Closure and Authority

## Prompt type
RED-TEAM

## Scope

This red-team attacks MET-19 (candidate closure ledger), MET-23 (EVL handoff
observation tracker), MET-24 (override evidence intake), and MET-26
(generated artifact classification). Each attack focuses on closure honesty
and authority neutrality.

## Attack surface

- Fake materialization claims that imply EVL/CDE/SEL accepted, adopted, or
  approved a candidate.
- Stale candidates hidden as `open` because no MET artifact tracks staleness.
- Candidates referenced without source artifacts.
- Authority-shaped language in MET-owned artifacts (decision, approve,
  enforce, certify, promote, execute, admit).
- Candidates that name no owner recommendation.
- Candidates not tied to a named failure_prevented or signal_improved.

## Findings

### F1 — must_fix — Stale items must remain visible
**finding:** A candidate ledger that drops undated items would let stale
items disappear from the operator surface.
**evidence:** `candidate_closure_ledger_record.json` includes
`FB-LEGACY-UNDATED-EXAMPLE` with `current_state = stale_candidate_signal`
and `age_days = "unknown"`.
**risk if unfixed:** Stale candidate pile grows invisibly.

### F2 — must_fix — Materialization observation must not imply owner action
**finding:** The EVL handoff tracker must record observations only and never
declare EVL accepted or adopted any candidate.
**evidence:** All `materialization_observation` values are constrained to
`none_observed | observed | blocked_observation | unknown`.
**risk if unfixed:** MET would silently inherit EVL authority.

### F3 — must_fix — Override evidence count must remain unknown without a canonical log
**finding:** Reporting `override_evidence_count = 0` in the absence of a
canonical log would create a false signal.
**evidence:** `override_evidence_intake_record.json` pins
`override_evidence_count` to `"unknown"`, `evidence_status = "absent"`, and
`reason_codes` includes `override_evidence_missing`.
**risk if unfixed:** Override posture would render as PASS by absence.

### F4 — must_fix — Candidate items must reference source_artifacts_used
**finding:** Closure ledger items without source references would let
unsourced recommendations reach the dashboard.
**evidence:** Every `candidate_items[]` entry carries
`source_artifacts_used` of length ≥ 1; the `met-19-33-artifacts.test.ts`
suite asserts this.
**risk if unfixed:** Operators would be unable to verify the closure target.

### F5 — should_fix — Authority-shaped vocabulary in MET docs
**finding:** Review docs that bare-name "decision", "approval",
"enforcement", "certification", or "promotion" without a safety suffix risk
authority-shape preflight diagnostics.
**evidence:** MET-21, MET-27, MET-28 use compound forms like
`enforcement_signal`, `certification_signal`, `promotion_signal`,
`decision_authority_input`.
**risk if unfixed:** Diagnostics would surface as advisory leaks.

### F6 — should_fix — Closure required-by criteria must be artifact-backed
**finding:** A closure target like "owner thinks it's ready" would not be
testable.
**evidence:** Each `closure_required_by` names an artifact-backed condition
(e.g., "EVL artifact reading long_horizon dimension status").
**risk if unfixed:** Closure would never be observable.

### F7 — observation — Owner recommendations remain advisory only
**observation:** Every closure ledger candidate, EVL handoff, and policy
candidate signal carries `target_owner_recommendation` or
`suggested_owner_system` as a recommendation only. Final adoption is the
canonical owner's call.

### F8 — observation — fold_candidate items remain in place
**observation:** MET-21 marks `override_audit_log_record.json` and
`eval_materialization_path_record.json` as `fold_candidate` but does not
remove them in this PR. Removal would happen only after canonical owners
read the replacement records.

## Classification summary

|severity|count|
|---|---|
|must_fix|4|
|should_fix|2|
|observation|2|

## Routing

All must_fix findings are addressed in `MET-28-closure-authority-fixes.md`.
should_fix findings are addressed in MET-28 where doing so is non-disruptive
and authority-neutral; otherwise tracked as feedback items.
