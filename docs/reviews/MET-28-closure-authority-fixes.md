# MET-28 — Fixes for Red-Team #1 (MET-27)

## Prompt type
FIX

## Scope

Fix every `must_fix` finding from `MET-27-closure-authority-redteam.md`.
should_fix findings are addressed where doing so is bounded and
authority-neutral.

## Fixes

### Fix F1 — Stale items remain visible

- **finding:** Stale candidates hidden as `open` would let the pile grow
  invisibly.
- **fix:** `candidate_closure_ledger_record.json` includes
  `FB-LEGACY-UNDATED-EXAMPLE` with
  `current_state = stale_candidate_signal` and `age_days = "unknown"`. The
  contract test
  `tests/metrics/test_met_19_33_contract_selection.py::test_candidate_closure_keeps_stale_visible_not_hidden`
  asserts a non-empty stale set.
- **files changed:**
  - `artifacts/dashboard_metrics/candidate_closure_ledger_record.json`
  - `tests/metrics/test_met_19_33_contract_selection.py`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-artifacts.test.ts`
- **tests added:**
  - `test_candidate_closure_keeps_stale_visible_not_hidden`
  - `MET-19 — candidate closure ledger invariants` jest block
- **residual risk:** Source feedback ledger may continue to emit undated
  items; the closure ledger records them as stale_candidate_signal rather
  than dropping them.

### Fix F2 — Materialization observation language only

- **finding:** Materialization that implies EVL accepted or adopted a
  candidate would inherit EVL authority.
- **fix:** EVL handoff tracker constrains
  `materialization_observation` to
  `none_observed | observed | blocked_observation | unknown`. The contract
  test
  `tests/metrics/test_met_19_33_contract_selection.py::test_evl_handoff_uses_observation_language_only`
  enforces it.
- **files changed:**
  - `artifacts/dashboard_metrics/evl_handoff_observation_tracker_record.json`
  - `tests/metrics/test_met_19_33_contract_selection.py`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-artifacts.test.ts`
- **tests added:**
  - `test_evl_handoff_uses_observation_language_only`
  - `MET-23 — EVL handoff uses observation language only` jest block
- **residual risk:** Future handoff items must continue to use the
  constrained observation set; the test pins the contract.

### Fix F3 — Override evidence count remains unknown without a canonical log

- **finding:** Reporting `0` for override evidence in the absence of a log
  would create a false PASS.
- **fix:** `override_evidence_intake_record.json` carries
  `override_evidence_count = "unknown"`,
  `evidence_status = "absent"`, and
  `reason_codes` includes `override_evidence_missing`. The API route's
  fail-closed branch in `apps/dashboard-3ls/app/api/intelligence/route.ts`
  pins `override_evidence_count` to `'unknown'` regardless of artifact
  presence.
- **files changed:**
  - `artifacts/dashboard_metrics/override_evidence_intake_record.json`
  - `apps/dashboard-3ls/app/api/intelligence/route.ts`
  - `tests/metrics/test_met_19_33_contract_selection.py`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-intelligence.test.ts`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-artifacts.test.ts`
- **tests added:**
  - `test_override_evidence_intake_holds_at_unknown_absent`
  - `test_intelligence_route_does_not_substitute_zero_for_override_evidence_count`
  - `MET-24 — override evidence intake stays absent without canonical log`
    jest block
- **residual risk:** None — the count is wired to remain unknown until a
  canonical log artifact lands and an owner-observed read replaces the
  unknown.

### Fix F4 — Candidate items reference source_artifacts_used

- **finding:** Items without source references could let unsourced
  recommendations reach the dashboard.
- **fix:** Every `candidate_items[]` entry includes a non-empty
  `source_artifacts_used` array. The API route filters out items without it
  via `filteredCandidateItems`. The contract test
  `test_candidate_closure_items_have_source_artifacts_used` enforces it.
- **files changed:**
  - `artifacts/dashboard_metrics/candidate_closure_ledger_record.json`
  - `apps/dashboard-3ls/app/api/intelligence/route.ts`
  - `tests/metrics/test_met_19_33_contract_selection.py`
- **tests added:**
  - `test_candidate_closure_items_have_source_artifacts_used`
  - `MET-19 — every candidate item has source_artifacts_used` jest block
- **residual risk:** None — filter operates on every loaded item.

### Fix F5 — Authority-shaped vocabulary in MET docs

- **finding:** Review docs naming bare authority words without a safety
  suffix risk authority-shape preflight diagnostics.
- **fix:** MET-21, MET-27, MET-28, MET-29, MET-30, MET-31, MET-32, MET-33
  use compound forms with safety suffixes (`signal`, `observation`, `input`,
  `recommendation`, `finding`, `evidence`, `advisory`, `request`,
  `candidate`, `hint`, `summary`, `report`) when describing authority
  surfaces.
- **files changed:**
  - `docs/reviews/MET-21-metric-usefulness-pruning-audit.md`
  - `docs/reviews/MET-27-closure-authority-redteam.md`
  - `docs/reviews/MET-28-closure-authority-fixes.md`
  - `docs/reviews/MET-29-simplification-debuggability-redteam.md`
  - `docs/reviews/MET-30-simplification-debuggability-fixes.md`
  - `docs/reviews/MET-31-artifact-integrity-redteam.md`
  - `docs/reviews/MET-32-artifact-integrity-fixes.md`
  - `docs/reviews/MET-33-final-hardening-review.md`
- **tests added:**
  - Existing
    `apps/dashboard-3ls/__tests__/api/met-04-18-learning-loop.test.ts`
    pattern is mirrored by the `MET-19-33 — authority vocabulary
    discipline` block in `met-19-33-artifacts.test.ts`.
- **residual risk:** Static authority-shape preflight remains the binding
  gate. should_fix items below the line are tracked as feedback items.

### Fix F6 — Closure required-by criteria are artifact-backed

- **finding:** "Owner thinks it's ready" is not testable.
- **fix:** Every `closure_required_by` in the closure ledger names an
  artifact-backed condition (e.g., "EVL artifact reading long_horizon
  dimension status", "REP replay_record exposing per-dimension status
  fields", "CDE-owned override audit log artifact present and populated").
- **files changed:**
  - `artifacts/dashboard_metrics/candidate_closure_ledger_record.json`
- **tests added:** none additional — the contract test
  `test_candidate_closure_items_have_source_artifacts_used` covers the
  source dimension; closure_required_by is reviewed in MET-29.
- **residual risk:** A future owner could ignore the closure-by criteria.
  That risk is owned by the canonical owner; MET signal-only.

## Residual must_fix items

None. All MET-27 must_fix findings are fixed.
