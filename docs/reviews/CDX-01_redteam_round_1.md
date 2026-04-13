# CDX-01 Red Team Round 1

## Scope
- missing-source bypass
- evidence insufficiency
- policy conflict
- comparison drift
- stale-active-set retrieval
- cross-artifact inconsistency
- shadow prompt / shadow route behavior

## Findings
1. **Missing-source bypass**: Context preflight accepted incomplete required-source coverage in legacy paths.
2. **Evidence insufficiency**: Promotion-readiness path accepted evidence presence without sufficiency scoring.
3. **Policy conflict**: No deterministic blocker reason when policy set is inactive/superseded.
4. **Comparison drift**: Comparison records were not required for route/prompt/model deltas.
5. **Stale-active-set retrieval**: Retired/superseded records could appear in default retrievals.
6. **Cross-artifact inconsistency**: No set-level validator emitted machine-readable reason codes.
7. **Shadow prompt/route behavior**: Untracked runtime changes were not represented as explicit blockers.

## Regression bindings
- `tests/test_next_phase_governance.py::test_context_preflight_blocks_when_requirements_not_met`
- `tests/test_next_phase_governance.py::test_evidence_and_abstention_wiring`
- `tests/test_next_phase_governance.py::test_simulation_quarantine_and_promotion_lock`
- `tests/test_next_phase_governance.py::test_consistency_active_set_query_and_signal`
