# SF-14 Regression Detection Review (Baseline vs Candidate)

## Overall Decision
FAIL

## Critical Regression Risks
- [ ] Coverage mismatch can pass as non-blocking in current gating.
- [ ] New failure identities are observed but not enforced in final decision.

## Blind Spots in Comparison
- Slice-level SF-07 artifacts are not consumed by the regression comparison path.
- Required slice degradation cannot currently hard-block release/canary through this path.
- Final exit/decision is driven only by hard_failures and warnings.

## Edge Case Failures
- Exact-threshold values pass due to strict inequality comparisons; no epsilon handling.
- Indeterminate outcomes are not directly modeled in regression gates; they are score-only.
- Ordering for tied worst regressions can vary with input ordering.
- Drift/replay signals are not integrated into this comparison decision path.

## Confirmed Strengths
- Policy-driven baseline vs candidate gating exists for core dimensions.
- Pass-level attribution computes per-case/per-pass deltas and unmatched counts.
- Determinism can be configured as a hard gate.
- SF-07 slice reporting correctly computes required-slice gaps and can count indeterminate as failure.

## Recommended Fixes (ordered)
1. Fail closed on coverage mismatch (case/slice set parity + minimum counts).
2. Enforce unmatched/partial-attribution as gating outcomes.
3. Integrate SF-07 slice artifacts into SF-14 baseline-vs-candidate decision.
4. Treat indeterminate as blocking (or require explicit approved override).
5. Stabilize ordering with deterministic composite sort keys.
6. Add threshold boundary/precision tests and deterministic replay tests.

## Residual Risk
High: concentrated degradation can still pass when aggregates look stable.
