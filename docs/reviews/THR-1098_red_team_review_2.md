# THR-1098 Red Team Review 2 — AI / eval / feedback loop

## Scope
AI route-by-risk, calibration, triage, counterfactual comparison, and feedback-loop quality/admission controls.

## Findings
1. **S2 — High-risk AI routes were not trace-tagged as governed route records.**
   - Fix: added `decide_ai_route_by_risk` with deterministic route output and trace linkage.
   - Test: `test_thr1098_admission_route_judge_triage_counterfactual`.

2. **S2 — Feedback candidate generation lacked explicit admission and rate-limit blocking seams.**
   - Fix: added `feedback_admission_gate` with recurrence/materiality/duplicate/rate-limit checks.
   - Test: `test_thr1098_feedback_review_quality_active_set_and_health`.

3. **S2 — Feedback-loop quality was not explicitly scored for stability/usefulness/duplication.**
   - Fix: added `evaluate_feedback_candidate_quality` quality scoring seam.
   - Test: `test_thr1098_feedback_review_quality_active_set_and_health`.

## Closure
All S2+ findings fixed in this execution phase.
