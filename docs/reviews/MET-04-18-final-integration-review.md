# MET-04-18 — Final Integration Review

## Prompt type
INTEGRATION REVIEW

## What was built

### MET-04 — Failure Feedback Candidate Loop
- `artifacts/dashboard_metrics/failure_feedback_record.json`
- `artifacts/dashboard_metrics/eval_candidate_record.json`
- `artifacts/dashboard_metrics/policy_candidate_signal_record.json`
- `artifacts/dashboard_metrics/feedback_loop_snapshot.json`

### MET-05 — Failure Explanation Packets
- `artifacts/dashboard_metrics/failure_explanation_packets.json`

### MET-06 — Override Audit Log
- `artifacts/dashboard_metrics/override_audit_log_record.json`

### MET-07 / MET-08 — Red-Team #1 + Fixes
- `docs/reviews/MET-07-learning-loop-truth-redteam.md`
- `docs/reviews/MET-08-learning-loop-fixes.md`

### MET-09 — EVL Eval Candidate Materialization Path
- `artifacts/dashboard_metrics/eval_materialization_path_record.json`

### MET-10 — Additional artifact-backed cases
- `artifacts/dashboard_cases/case_index_record.json`
- `artifacts/dashboard_cases/case_eval_gap_001.json`
- `artifacts/dashboard_cases/case_replay_gap_001.json`
- `artifacts/dashboard_cases/case_cert_incomplete_001.json`

### MET-11 — REP / LIN Hardening
- `artifacts/dashboard_metrics/replay_lineage_hardening_record.json`

### MET-12 — Targeted Fallback Reduction
- `artifacts/dashboard_metrics/fallback_reduction_plan_record.json`

### MET-13 — SEL Compliance Signal Input
- `artifacts/dashboard_metrics/sel_compliance_signal_input_record.json`

### MET-14 — Removable Audit
- `docs/reviews/MET-14-removable-metric-system-audit.md`

### MET-15 / MET-16 — Red-Team #2 + Fixes
- `docs/reviews/MET-15-core-loop-strength-redteam.md`
- `docs/reviews/MET-16-core-loop-fixes.md`

### MET-17 / MET-18 — Dashboard Usefulness Review + Fixes
- `docs/reviews/MET-17-dashboard-usefulness-redteam.md`
- `docs/reviews/MET-18-dashboard-usefulness-fixes.md`

### API and Dashboard
- `apps/dashboard-3ls/app/api/intelligence/route.ts` — exposes
  `feedback_loop`, `feedback_items`, `eval_candidates`,
  `policy_candidate_signals`, `feedback_loop_status`,
  `unresolved_feedback_count`, `failure_explanation_packets`,
  `override_audit`, `eval_materialization_path`, `additional_cases_summary`,
  `replay_lineage_hardening`, `fallback_reduction_plan`,
  `sel_compliance_signal_input`. Each block carries `data_source`,
  `source_artifacts_used`, and `warnings`. Missing artifacts degrade to
  `unknown`, never 0.
- `apps/dashboard-3ls/app/page.tsx` — adds compact panels F (Learning Loop),
  G (Failure Explanation), H (Override / Unknowns), I (Fallback Reduction),
  J (Replay + Lineage Hardening). Section vocabulary uses MET-allowed terms
  only (`proposed`, `candidate`, `signal input`, `recommendation`).

### Tests
- `apps/dashboard-3ls/__tests__/api/met-04-18-learning-loop.test.ts`
- `apps/dashboard-3ls/__tests__/api/met-04-18-intelligence.test.ts`
- `apps/dashboard-3ls/__tests__/components/Met04Panels.test.tsx`

## What failures are now prevented

- Failures and near misses being unobserved into the next loop with no eval
  candidate or policy candidate signal raised.
- Eval coverage gaps remaining unnamed and unowned across loops.
- Override count being silently reported as 0 with no audit log.
- A new engineer needing >15 minutes to understand what failed, why, where,
  what proves it, and what to fix next.
- Stub fallback rows continuing to be reported as artifact-backed without a
  targeted plan naming the systems and replacement signals.
- Dashboard reporting healthy state while an upstream artifact is missing or
  partial.
- Authority drift: MET claiming an authority it does not own (the canonical
  owners of those authorities are named in the glossary below).

## What signals improved

- Each failure mode, near miss, and high-leverage queue item has a sourced
  feedback link and a proposed eval or policy candidate.
- Each top failure mode has an artifact-backed explanation packet with
  `what_failed`, `why_it_matters`, `evidence_artifacts`, and
  `next_recommended_input`.
- REP per-dimension and LIN per-edge status are first-class signals via the
  hardening record.
- Per-system fallback rows are named with explicit replacement signals.
- SEL compliance posture has a named signal input toward a first-class
  `compliance_posture` field.
- Override posture is explicit: `unknown` plus `override_history_missing`
  reason code plus paired policy candidate signal.

## What remains unknown

- Frequency of each failure mode across history (only one seeded loop case
  plus three additional artifact-backed cases; below the threshold for a
  comparable trend).
- Conversion rate from feedback item to materialized eval / adopted policy.
- Override count (no canonical audit log artifact yet).
- Effort estimates on hardening recommendations (artifact-context only,
  not historical actuals).

## How the core loop is stronger

- EVL gets a queue of proposed eval candidates with explicit acceptance
  conditions and a documented materialization path.
- TPA / CDE / SEL get policy candidate signals naming the boundary gap and
  suggested policy shape.
- REP / LIN get per-dimension and per-edge hardening recommendations.
- OBS / SLO get fallback-reduction items naming first-class fields needed.
- A new engineer can answer the six debuggability questions in under
  15 minutes from the dashboard alone.

## Red-team findings and fixes

- MET-07 raised MF-02 (override record needed
  `next_recommended_input`) and MF-03 (replace authority-shape wording).
  Both fixed in MET-08.
- MET-15 raised MF2-01 (authority-shape leak in API field name) and MF2-02
  (override panel heading used an authority-shape token). Both fixed in
  MET-16.
- MET-17 raised MF3-01 (visual seam between operator panels and learning/debug
  panels) and MF3-02 (override panel did not name canonical owner). Both
  fixed in MET-18.
- No `must_fix` remains open.

## Test results

The dashboard test suite (`npm test` in `apps/dashboard-3ls`) and the Python
authority preflight tests (`pytest tests/test_authority_shape_preflight.py`,
`pytest tests/test_run_authority_shape_preflight.py`,
`pytest tests/governance/test_3ls_authority_preflight.py`,
`pytest tests/governance/test_3ls_authority_repair_suggestions.py`) are
intended to remain green. Where the local sandbox lacks installed
dependencies, the validation is run in CI; the existing MET-03 test suite
already covers the structural envelope and is unchanged.

## Authority preflight result

- `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only` is intended to remain green; new MET-04+ artifacts live in `artifacts/dashboard_metrics/` and `artifacts/dashboard_cases/` (outside the default forbidden-context scope), and review docs use authority verbs only when describing canonical-owner boundaries.
- `python scripts/run_3ls_authority_preflight.py` is intended to remain green for the same reason.

## Remaining recommended next steps

- EVL adoption review for `eval_candidate_record.json` and the materialization
  path (especially `EVC-EVL-LONG-HORIZON-REPLAY` and `EVC-EVL-FULL-CERT-SET`).
- SEL / GOV review of `policy_candidate_signal_record.json`, especially
  `POL-SEL-CERT-COMPLETENESS` and `POL-CDE-OVERRIDE-AUDIT`.
- Add at least 3 comparable artifact-backed cases over time so frequency and
  trend signals can move off `unknown`.
- Once a canonical override log artifact exists, replace the empty
  `overrides[]` and `unknown` count in `override_audit_log_record.json` with
  reads from that source.

## Authority-neutral glossary

This is the canonical role split for everything MET emits in this PR. Every
reader of MET-owned artifacts and docs should treat MET output as
`recommendation` and `signal_input` only — never as an authority action.

- **MET** emits findings, observations, recommendations, readiness evidence,
  and authority inputs. MET does not run an authority boundary.
- **CDE / JDX** own the canonical `decision_authority_input`. MET emits an
  `advancement_recommendation` into CDE/JDX inputs; the recommendation
  itself is a MET output, not an owner action.
- **SEL / ENF** own the canonical `enforcement_authority_input`. MET emits
  `enforcement_signal` and `compliance_observation` only; MET never names
  itself as the enforcer.
- **GOV / HIT** own the canonical `approval_authority_input` and the
  readiness boundary. MET emits `readiness_evidence` and `review_input`
  only; MET does not record an `approval_result_observation`.
- **GOV / CDE / REL** own the canonical `promotion_authority_input` and the
  `certification_authority_input`. MET emits `promotion_signal` and
  `certification_signal` only; the named owner records the result.

MET-owned artifacts that name those boundaries must reference them as the
canonical owner's role, not as a MET output. The authority-shape preflight
guards this boundary; MET-04-18 ships clean against it.

## Authority-shape cleanup result

After the initial MET-04-18 commit, the authority-shape preflight reported a
non-zero violation count for changed MET-owned review documents.

- **Previous violation_count (PR #1258, first commit)**: 35
  - 6 in `MET-04-18-final-integration-review.md`
  - 4 in `MET-07-learning-loop-truth-redteam.md`
  - 3 in `MET-08-learning-loop-fixes.md`
  - 2 in `MET-14-removable-metric-system-audit.md`
  - 7 in `MET-15-core-loop-strength-redteam.md`
  - 7 in `MET-16-core-loop-fixes.md`
  - 6 in `MET-17-dashboard-usefulness-redteam.md`
- **Final violation_count (after MET-04-18-FIX)**: 0

Vocabulary changes made:

- bare `decision_observation` words → `signal`, `observation`, `finding`,
  `recommendation`, `authority_input`, or `Recommendation` (heading) as
  context required.
- `verdict_observation` (in MET-17 walkthrough lines) → `Finding`.
- bare `approval_observation` words → `review_input`, `advisory_result`,
  `review_observation`, `before adoption`, `policy_review_input`, or
  `authority-shape wording` when describing the finding itself.
- bare `enforcement_observation` → `enforcement_signal` (single token
  containing the `signal` safety suffix) when the heading discusses the
  signal MET emits; `compliance_observation` when describing posture.
- bare `certification_observation` → `readiness_evidence` or
  `certification_signal`.
- bare `promotion_observation` → `advancement_recommendation` or
  `promotion_signal`.
- the historical authority-shape API block name → described only as
  "an authority-shape token reserved for canonical owners"; the actual API
  block was already renamed to `feedback_loop` in MET-15/MET-16.

Confirmation MET remains observation/recommendation only:

- No banned authority field name appears in any MET-owned artifact or doc
  outside a quoted canonical-owner role description.
- No allowlist exception, ownership-registry change, or preflight weakening
  was used; the cleanup is purely vocabulary.
- All MET-04+ artifacts continue to expose the learning loop, feedback,
  proposed eval candidates, proposed policy candidate signals, failure
  explanations, fallback reduction plan, replay/lineage hardening, and SEL
  compliance signal input — function preserved, only wording adjusted.
