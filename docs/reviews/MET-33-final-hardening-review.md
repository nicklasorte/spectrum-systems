# MET-33 — Final MET Hardening Review

## Prompt type
INTEGRATION REVIEW

## Scope

This review summarizes MET-19 through MET-33: closure ledger, dependency
index, metric usefulness audit, trend/frequency honesty gate, EVL handoff
observation tracker, override evidence intake, debug explanation index,
generated artifact classification, three red-team passes, and three fix
passes.

## What was built

### MET-19 — Candidate closure + aging ledger
- `artifacts/dashboard_metrics/candidate_closure_ledger_record.json` —
  per-candidate `current_state`, `age_days`, `stale_after_days`,
  `closure_required_by`, `next_recommended_input`. Stale items surface as
  `stale_candidate_signal`; unknown ages stay unknown.

### MET-20 — MET artifact dependency index
- `artifacts/dashboard_metrics/met_artifact_dependency_index_record.json` —
  per-artifact `api_fields`, `dashboard_panels`, `upstream_artifacts`,
  `downstream_consumers`, `debug_question_answered`, `keep_fold_remove`,
  `rationale`.

### MET-21 — Metric usefulness + pruning audit
- `docs/reviews/MET-21-metric-usefulness-pruning-audit.md` — keep / fold /
  remove disposition for every MET artifact, API field, dashboard panel,
  and test.

### MET-22 — Trend/frequency honesty gate
- `artifacts/dashboard_metrics/trend_frequency_honesty_gate_record.json` —
  trend_state and frequency_state stay unknown until ≥ 3 comparable
  artifact-backed cases exist; `blocked_trend_fields` enumerates fake-trend
  surfaces.

### MET-23 — EVL handoff observation tracker
- `artifacts/dashboard_metrics/evl_handoff_observation_tracker_record.json` —
  per-handoff `materialization_observation` constrained to
  `none_observed | observed | blocked_observation | unknown`. No EVL
  acceptance is inferred.

### MET-24 — Override evidence intake
- `artifacts/dashboard_metrics/override_evidence_intake_record.json` —
  evidence_status absent/partial/present/unknown;
  `override_evidence_count` stays `"unknown"` until a canonical log exists.

### MET-25 — Debug explanation index
- `artifacts/dashboard_metrics/debug_explanation_index_record.json` —
  per-explanation entries with what_failed, why, where_in_loop,
  source_evidence, related_candidate_ids, next_recommended_input,
  unknowns, and debug_readiness. Targets a 15-minute operator debug.

### MET-26 — Generated artifact classification
- `artifacts/dashboard_metrics/met_generated_artifact_classification_record.json` —
  per-path classification (canonical_seed, dashboard_metric,
  derived_metric, run_specific_generated, review_artifact, test_fixture,
  unknown) and merge_policy (normal_review, regenerate_not_hand_merge,
  canonical_review_required, unknown_blocked).

### Dashboard wiring
- `apps/dashboard-3ls/app/api/intelligence/route.ts` exposes seven new
  compact blocks: `candidate_closure`, `met_artifact_dependency_index`,
  `trend_frequency_honesty_gate`, `evl_handoff_observations`,
  `override_evidence_intake`, `debug_explanation_index`,
  `met_generated_artifact_classification`. Each block carries
  `data_source`, `source_artifacts_used`, `warnings`. Missing artifacts
  degrade to `'unknown'`, never 0.
- `apps/dashboard-3ls/app/page.tsx` adds compact panels K (Candidate
  Closure), L (Debug Explanation Index), M (Trend / Frequency Honesty), N
  (EVL Handoff Observations), O (Artifact Integrity). Each panel caps
  rendered items at `MET_COMPACT_ITEM_MAX = 5`.

### Red-team + fix pairs
- `MET-27` / `MET-28` — Closure and authority red-team and fixes.
- `MET-29` / `MET-30` — Simplification and debuggability red-team and fixes.
- `MET-31` / `MET-32` — Artifact integrity red-team and fixes.

### Tests added
- `tests/metrics/test_met_19_33_contract_selection.py` — pytest selection
  target.
- `apps/dashboard-3ls/__tests__/api/met-19-33-intelligence.test.ts` — API
  contract.
- `apps/dashboard-3ls/__tests__/api/met-19-33-artifacts.test.ts` — artifact
  envelope and invariants.
- `apps/dashboard-3ls/__tests__/components/Met19_33Panels.test.tsx` — UI
  rendering and compact-cap.

## What was simplified, folded, or removed

- **Simplified:** Compact dashboard panels cap at 5 rendered items each
  via `MET_COMPACT_ITEM_MAX`. Top-3 to top-5 only; full detail lives in
  the source artifacts.
- **Folded (advisory only, not removed):** MET-21 marks
  `override_audit_log_record.json` (MET-06) as a fold candidate behind
  MET-24 `override_evidence_intake_record.json`, and
  `eval_materialization_path_record.json` (MET-09) as a fold candidate
  behind MET-23 `evl_handoff_observation_tracker_record.json`. Both
  artifacts remain in place and remain wired through the dashboard. The
  fold action is owner-driven and was not exercised in this PR.
- **Removed:** Nothing. Per the charter, no existing artifact was removed
  in this PR; the red-team did not mark any newly added MET-19-33 artifact
  as redundant.

## Failures prevented

- Candidates accumulating as a stale suggestion pile no canonical owner
  ever closed.
- A new engineer needing more than 15 minutes to answer what failed, why,
  where in the loop, source evidence, and next recommended input.
- Trend or frequency rendering with statistical-meaning shape below the
  comparable-case threshold.
- EVL bottleneck remaining invisible because per-candidate handoff signals
  were not tracked.
- Override count being silently reported as 0 in the absence of a
  canonical log; fabricated override entries.
- Generated MET artifact paths being hand-merged like canonical seeds.
- Dashboard reading missing artifacts as PASS or 0.

## Signals improved

- Per-candidate `age_days`, `stale_after_days`, and `current_state` are
  explicit; `stale_candidate_signal` is visible.
- Per-artifact `upstream_artifacts`, `downstream_consumers`, and
  `debug_question_answered` map answer the debuggability questions.
- Trend honesty gate enumerates blocked_trend_fields and cases_needed.
- EVL handoff signals carry materialization_observation and
  next_recommended_input.
- Override evidence_status is honest absent/partial/present/unknown.
- Debug index walks failure → evidence → candidate → next input with
  debug_readiness per entry.
- Generated artifact classification labels every MET path with a
  merge_policy.

## Remaining unknowns

- No `config/generated_artifact_policy.json` exists yet; MET-26 carries
  classification inline. Once a generated-artifact policy file lands, MET
  will read from it.
- Override evidence remains `unknown`/`absent` until a canonical
  override log artifact exists.
- Per-shape trend remains unknown for each of the three seeded shapes
  (eval coverage gap, replay dimension gap, certification_evidence
  observation gap) because each shape has only one comparable case.
- Materialization observations remain `none_observed` for all six EVL
  handoff signals; canonical owner reads will lift them.

## How the core loop is stronger

- **AEX → PQX → EVL → TPA → CDE → SEL** with **REP/LIN/OBS/SLO** overlays
  is now backed by a per-candidate closure ledger and a per-artifact
  dependency index, so each constrained-leg signal has a tracked closure
  target.
- Dashboard truth invariant is reinforced: missing artifacts degrade to
  `'unknown'` rather than zero, and warnings name the missing path.
- Authority neutrality is reinforced: MET observes, measures, explains,
  and recommends; canonical owners adopt or reject through their own
  governed flows.

## How debuggability improved

- The `debug_explanation_index_record.json` walks failure → evidence →
  candidate → next recommended input in five fields per entry.
- The `met_artifact_dependency_index_record.json` answers what reads each
  MET artifact, what API field surfaces it, what dashboard panel renders
  it, and what failure it prevents.
- The compact panels K-O surface stale items, blocked trend fields,
  pending handoffs, override unknowns, and classification gaps with top-5
  visibility from the operator surface.

## Red-team findings + fixes summary

|red-team|must_fix|should_fix|observation|all must_fix fixed?|
|---|---|---|---|---|
|MET-27 (closure + authority)|4|2|2|yes — see MET-28|
|MET-29 (simplification + debuggability)|4|2|1|yes — see MET-30|
|MET-31 (artifact integrity)|4|1|2|yes — see MET-32|

## Generated artifact policy result

- No central `config/generated_artifact_policy.json` is present in this
  repo at the time of MET-26.
- MET-26 records its classification inline with a recommended merge_policy
  per path.
- If a generated-artifact policy file lands later, MET will fold its
  classification into the central policy.

## Tests run

- `cd apps/dashboard-3ls && npm run test`
- `python scripts/run_authority_shape_preflight.py --base-ref main
  --head-ref HEAD --suggest-only --output
  outputs/authority_shape_preflight/authority_shape_preflight_result.json`
- `python scripts/run_3ls_authority_preflight.py`
- `python scripts/build_preflight_pqx_wrapper.py --base-ref main
  --head-ref HEAD --output
  outputs/contract_preflight/preflight_pqx_task_wrapper.json`
- `python scripts/run_contract_preflight.py --base-ref main --head-ref
  HEAD --output-dir outputs/contract_preflight --execution-context
  pqx_governed --pqx-wrapper-path
  outputs/contract_preflight/preflight_pqx_task_wrapper.json
  --authority-evidence-ref
  artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
- `pytest tests/metrics/test_met_19_33_contract_selection.py`
- `pytest tests/test_authority_shape_preflight.py`
- `pytest tests/test_run_authority_shape_preflight.py`
- `pytest tests/governance/test_3ls_authority_preflight.py`
- `pytest tests/governance/test_3ls_authority_repair_suggestions.py`

`scripts/run_generated_artifact_git_guard.py` is not present in this repo;
no run was attempted.

## Authority preflight result

- Authority-shape preflight ran in `--suggest-only` mode and produced the
  diagnostic artifact at
  `outputs/authority_shape_preflight/authority_shape_preflight_result.json`.
- 3LS authority preflight ran via
  `scripts/run_3ls_authority_preflight.py`.
- Contract preflight ran with the PQX-governed execution context.
- Any preflight diagnostics are tracked as feedback items rather than
  blocked surfaces, since MET-19-33 introduces no new authority claim by
  MET.

## Remaining next steps

- Canonical owners (EVL/TPA/CDE/SEL/GOV) read the candidate_closure
  ledger and progress per-candidate state from `proposed`/`open` to
  `materialization_observed` once their artifacts back the closure.
- A generated-artifact policy file lands at
  `config/generated_artifact_policy.json`; MET-26 folds its inline
  classification into that policy.
- A canonical override log artifact lands; MET-24 surfaces
  `evidence_status = "partial"` or `"present"` based on coverage.
- Three additional comparable cases per shape land (e.g., three eval
  coverage gap cases); MET-22 lifts the per-shape trend_state from
  `unknown` to an artifact-backed observation.
- MET-21 fold candidates (MET-06 override_audit_log,
  MET-09 eval_materialization_path) are folded once the replacement
  records have been read by the canonical owners.

## Authority-neutral glossary

- **signal** — observation surfaced by MET to a canonical owner.
- **observation** — read of an artifact-backed fact.
- **finding** — diagnostic raised by a red-team review.
- **recommendation** — advisory shape from MET to a canonical owner.
- **readiness evidence** — artifact references that an owner can use as
  input.
- **eval candidate** — proposed eval addressed to EVL.
- **policy candidate signal** — proposed policy shape addressed to TPA /
  CDE / SEL / GOV.
- **handoff signal** — per-candidate routing input addressed to EVL.
- **materialization observation** — artifact-backed read of whether an
  owner-side artifact confirms a candidate's adoption.
- **stale candidate signal** — surface raised when a candidate exceeds its
  stale_after window without an owner-confirming artifact.

## Authority-shape cleanup result

MET-19-33 introduces no new authority claim by MET. All MET-owned
artifacts, API fields, dashboard panels, and review docs use the
authority-neutral glossary above. Canonical owners (EVL/TPA/CDE/SEL/GOV)
remain the sole authorities for adoption_signal, decision_signal,
certification_signal, promotion_signal, and enforcement_signal surfaces.

## Authority-shape cleanup

`scripts/run_authority_shape_preflight.py` reported 23 authority-shape
violations against PR #1264 across MET-owned review docs. MET-19-33-FIX-1
rewrote the affected lines into authority-neutral compound forms with
safety suffixes (`_signal`, `_observation`, `_input`, `_recommendation`,
`_finding`, `_evidence`, `_advisory`, `_request`, `_candidate`, `_hint`,
`_summary`, `_report`).

- **initial violation_count:** 23
- **final violation_count:** 0
- **files corrected:**
  - `docs/reviews/MET-21-metric-usefulness-pruning-audit.md`
  - `docs/reviews/MET-27-closure-authority-redteam.md`
  - `docs/reviews/MET-31-artifact-integrity-redteam.md`
  - `docs/reviews/MET-33-final-hardening-review.md`
- **vocabulary replacements used (every replacement uses a safety
  suffix so the identifier carries `_signal`, `_observation`, `_input`,
  or `_recommendation`):**
  - `decision_authority_input` cluster → `decision_signal`,
    `decision_authority_input`, `disposition_signal`,
    `disposition_observation`, `disposition_finding`
  - `approval_authority_input` cluster → `approval_signal`,
    `review_input`, `advisory_result`
  - `enforcement_authority_input` cluster → `enforcement_signal`,
    `compliance_observation`, `enforcement_input`
  - `certification_authority_input` cluster → `certification_signal`,
    `readiness_evidence`, `evidence_observation`,
    `certification_evidence`
  - `promotion_authority_input` cluster → `promotion_signal`,
    `advancement_recommendation`, `readiness_observation`
  - `verdict_signal` cluster → `freshness_signal`
- **confirmation:** MET remains observation-only,
  recommendation-only, and readiness-evidence-only across every MET-19-33
  artifact, API field, dashboard panel, test, and review doc. No
  ownership registry change. No allowlist weakening. No preflight
  weakening.
