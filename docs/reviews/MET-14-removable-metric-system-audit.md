# MET-14 — Removable Metric / System Audit

## Prompt type
AUDIT

## Scope
Audit MET and dashboard metric artifacts. For each: name, `failure_prevented`,
`signal_improved`, keep / fold / remove, reason, dependency impact.

Rule: if it prevents no failure and improves no signal, recommend fold or
remove.

## Audit table

| Artifact / Panel | failure_prevented | signal_improved | Decision | Reason | Dependency impact |
|---|---|---|---|---|---|
| `bottleneck_record.json` | Bottleneck staying anecdotal | Per-system warning/block counts with sources | keep | First-class bottleneck signal with confidence label | `/api/intelligence` exposes; UI consumes |
| `leverage_queue_record.json` | Recommendations without source | Sourced leverage items with weights | keep | First-class leverage signal | `/api/intelligence`; UI |
| `risk_summary_record.json` | Counts substituted by 0 | Proof-chain coverage and top risks | keep | First-class risk envelope | `/api/intelligence`; UI |
| `failure_feedback_record.json` (MET-04) | Failures dropping with no candidate | Sourced links failure -> candidate | keep | Closes the learning loop | API / UI |
| `eval_candidate_record.json` (MET-04) | Eval gaps unowned | Proposed eval candidates with acceptance condition | keep | EVL adoption path | API / UI |
| `policy_candidate_signal_record.json` (MET-04) | Policy gaps unowned | Proposed policy candidate signals | keep | Owner-system path | API / UI |
| `feedback_loop_snapshot.json` (MET-04) | Loop volume hidden | Single-screen learning loop snapshot | keep | Operator readability | API / UI |
| `failure_explanation_packets.json` (MET-05) | New engineer >15 min to debug | Per-failure explanation with debug summary | keep | Debuggability | API / UI |
| `override_audit_log_record.json` (MET-06) | Override count silently 0 | Explicit unknown + reason code | keep | Fail-closed unknown | API / UI |
| `eval_materialization_path_record.json` (MET-09) | EVL bottleneck recurring with no path | Named path candidate -> EVL artifact | keep | Bottleneck attack | API / UI |
| `dashboard_cases/case_*.json` (MET-10) | Single-case-only metrics | 3 comparable artifact-backed cases | keep | Triangulation | API summary only |
| `replay_lineage_hardening_record.json` (MET-11) | Causality gaps un-named | Per-dimension / per-edge signal | keep | Debuggability | API / UI |
| `fallback_reduction_plan_record.json` (MET-12) | Boil-the-ocean fallback projects | Targeted high-leverage rows only | keep | Bounded scope | API / UI |
| `sel_compliance_signal_input_record.json` (MET-13) | Observe-only ambiguity | Suggested compliance_posture field | keep | Authority-neutral input | API / UI |
| Existing MET-03 panels (Bottleneck / Risk / Leverage) | Same as backing artifacts | Same | keep | No redundancy with MET-04+ panels | UI |

## Removable / foldable

None. Every artifact in this PR justifies itself by `failure_prevented` and
`signal_improved`. The MET-15 red-team revisits redundancy after the dashboard
UI is wired, so any over-paneling discovered there will be folded in MET-16.

## Notes on potential redundancy

- `failure_feedback_record` and `eval_candidate_record` could in principle be
  collapsed into one. They are kept separate because feedback_items[] also
  point at policy_candidate_signal_record (not just eval), and the
  `feedback_status` lifecycle is different from the eval `status` field.
- `failure_explanation_packets` and `failure_mode_dashboard_record` are not
  redundant: the seed record names the failure mode; the explanation packet
  adds debug evidence and next recommended input.

## Decision

No removals in this PR. MET-15 will re-test after the UI is wired. Any
fold/remove forced by MET-15 must_fix will be applied in MET-16.
