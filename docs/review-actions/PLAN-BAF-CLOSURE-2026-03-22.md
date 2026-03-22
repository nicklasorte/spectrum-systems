# PLAN — BAF Closure Final Bounded Pass (2026-03-22)

## Prompt type
BUILD (bounded closure patch against already hardened BAF surfaces)

## Declared scope
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `tests/test_enforcement_engine.py`
- `tests/test_replay_engine.py`
- `docs/reviews/2026-03-22-baf-closure-review.md`

## Audit/implementation steps
1. Audit downstream BAF decision consumers for status coercion/default/fallback weakening.
2. Audit legacy `enforce_budget_decision(...)` callers and close non-approved access fail-closed.
3. Add narrow regression tests for each confirmed defect.
4. Run targeted runtime tests for modified boundaries.
5. Run changed-scope verification and record result in closure review artifact.
6. Publish closure judgment and residual-risk/reopen-trigger record.

## Out-of-scope (explicit)
- No schema churn unless a concrete mismatch is confirmed.
- No module restructuring/refactor.
- No unrelated runtime/control-chain behavior changes.
