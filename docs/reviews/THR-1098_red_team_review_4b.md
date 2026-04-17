# THR-1098 Red Team Review 4B — feedback-loop abuse

## Scope
Abuse vectors: noisy failures, duplicate candidates, weak rollback hooks, triage misclassification pressure.

## Findings
1. **S2 — Regression path lacked explicit rollback signal when learned changes increase failure rate.**
   - Fix: added `feedback_rollback_guard` revocation/rollback-required signal.
   - Test: `test_thr1098_feedback_review_quality_active_set_and_health`.

2. **S2 — Closed-loop classifier coverage was implicit rather than explicit.**
   - Fix: added `feedback_loop_core` closed-loop classification completeness gate over canonical failure taxonomy buckets.
   - Test: `test_thr1098_feedback_review_quality_active_set_and_health`.

3. **S1 — Counterfactual outputs not explicitly structured for A/B deltas.**
   - Fix: added `compare_counterfactual_variants` deterministic difference artifact.

## Closure
All S2+ findings fixed in this execution phase.
