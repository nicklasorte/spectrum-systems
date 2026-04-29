# MET-RT-03 Trend / Outcome Honesty Red-Team

## Prompt type
REVIEW

## Scope
- `trend_frequency_honesty_gate_record`
- `comparable_case_qualification_gate_record`
- `outcome_attribution_record`
- `failure_reduction_signal_record`
- `recurring_failure_cluster_record` / `recurrence_severity_signal_record`

## Attack Patterns
1. **Fake trend.**
   - Attack: emit `trend_state = increasing` from a single sample.
   - Risk: prioritisation is biased by an unverified trend.

2. **Fake improvement.**
   - Attack: claim an `observed_delta` without a paired before/after artifact.
   - Risk: regressions hide as fixed.

3. **Cherry-picked cases.**
   - Attack: include only the cases that match the desired trend; exclude
     comparable but inconvenient cases.
   - Risk: comparable_case_count appears to meet threshold but content is
     filtered.

4. **Weak attribution.**
   - Attack: pair an after-state with an unrelated artifact.
   - Risk: attribution_confidence is inflated.

## Findings

### must_fix
1. **Trend stays unknown until 3 comparable cases.**
2. **Outcome status must be one of insufficient_evidence / partial / observed
   / unknown** — `observed` requires non-empty before AND after evidence_refs.
3. **Recurrence stays insufficient_cases until the 3-case threshold is met.**

### should_fix
1. Each outcome entry carries `attribution_confidence` and a reachable
   `next_recommended_input`.
2. Cherry-picking is mitigated by requiring `same failure_shape`,
   `same affected_systems`, `same evaluated_fields`, `same source_type` for
   comparability (qualification_gate rules unchanged).

### observation
1. Today's recurrence clusters have insufficient_cases; severity remains
   unknown.
2. Outcome attribution entries are status `insufficient_evidence` or
   `unknown` — no fake observed claims.
