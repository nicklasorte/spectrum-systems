# MET-RT-04 Confidence / Gaming Red-Team

## Prompt type
REVIEW

## Scope
- `recommendation_accuracy_record`
- `calibration_drift_record`
- `signal_confidence_record`
- `metric_gaming_detection_record`
- `misleading_signal_detection_record`
- `signal_integrity_check_record`

## Attack Patterns
1. **Overconfidence.**
   - Attack: emit `confidence_level: high` with a single evidence_ref.
   - Risk: dashboard renders a thin signal as actionable certainty.

2. **Misleading green.**
   - Attack: status remains green while underlying outcome attribution
     contradicts the recommendation.
   - Risk: regressions look fixed.

3. **Gamed metrics.**
   - Attack: substitute 0 for unknown to reduce a fallback / unknown count.
   - Risk: green status is purchased at the cost of signal honesty.

4. **Stale artifacts rendered as current.**
   - Attack: stale_after_days passes without the dashboard surfacing a
     `stale_candidate_signal`.
   - Risk: candidates rot in the queue silently.

## Findings

### must_fix
1. **High confidence must require minimum 3 evidence_refs.**
2. **Misleading-signal detection must flag stale signals and high-confidence
   thin-evidence cases.**
3. **API blocks must degrade to unknown — never substitute 0.**

### should_fix
1. Calibration buckets stay unknown / insufficient_cases until enough paired
   outcomes exist.
2. Signal integrity aggregate carries `overall_integrity_state`.

### observation
1. `metric_gaming_detection_record` enumerates rules and tracks today's
   observations. No flagged gaming today; misleading-signal flags are
   surfaced for stale + thin-evidence cases.
