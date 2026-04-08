# PLAN-BUNDLE-01-EXTENDED-FIX-02-2026-04-08

## Objective
Upgrade BUNDLE-01-EXTENDED harness runner from scaffold to real validation output generation with fail-closed enforcement and stronger tests.

## Scope
- Upgrade `scripts/run_harness_integrity_bundle.py` with real integrity/transition/state/policy/failure/trace/replay checks.
- Ensure all 10 required output artifacts are computed and emitted to `outputs/harness_bundle_review/`.
- Strengthen `tests/test_harness_integrity_bundle.py` assertions for non-empty outputs, failure-scenario coverage, and cross-system comparisons.
- Update `docs/reviews/harness_integrity_review.md` to reference only generated outputs backed by code.

## Files planned
1. `scripts/run_harness_integrity_bundle.py` (MODIFY)
2. `tests/test_harness_integrity_bundle.py` (MODIFY)
3. `docs/reviews/harness_integrity_review.md` (MODIFY)

## Non-goals
- No new execution paths outside existing governed seams.
- No policy-gate weakening.
- No unrelated refactors.
