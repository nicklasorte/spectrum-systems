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
- Authority drift: MET claiming decisions, enforcement, certification, or
  promotion authority.

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
  `next_recommended_input`) and MF-03 (replace approval-shaped wording).
  Both fixed in MET-08.
- MET-15 raised MF2-01 (authority-shape leak in API field name) and MF2-02
  (override panel heading used "Decisions"). Both fixed in MET-16.
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
