# Plan — AUTO-PUBLICATION-06-01 — 2026-04-11

## Prompt type
BUILD

## Roadmap item
AUTO-PUBLICATION-06-01

## Objective
Remove manual dashboard refresh by wiring a fail-closed post-run publication hook that emits trigger/enforcement/preflight/deploy-gate artifacts and blocks progression on stale or partial public truth.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-AUTO-PUBLICATION-06-01-2026-04-11.md | CREATE | Required written plan before >2 file changes |
| scripts/run_rq_master_36_01.py | MODIFY | Emit refresh trigger manifest and invoke post-run refresh hook only on successful runs |
| scripts/refresh_dashboard.sh | MODIFY | Add atomic publication bundle metadata + enforcement/preflight/deploy gate artifact emission |
| scripts/validate_dashboard_public_artifacts.py | MODIFY | Enforce refresh/public truth fail-closed checks and emit enforcement artifact |
| tests/test_refresh_dashboard_publication.py | MODIFY | Validate auto-refresh invocation/trigger and negative failed-run behavior |
| tests/test_validate_dashboard_public_artifacts.py | MODIFY | Validate enforcement/deploy stale and broken publication gates |
| docs/reviews/AUTO-PUBLICATION-06-01-DELIVERY-REPORT.md | CREATE | Required delivery report for execution completion artifacts |
| docs/reviews/RVW-AUTO-PUBLICATION-06-01.md | CREATE | Required review report for authority and fail-closed checks |
| artifacts/rq_master_36_01/auto_publication_checkpoint_summary.json | CREATE | Required checkpoint summary artifact |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_refresh_dashboard_publication.py -q`
2. `pytest tests/test_validate_dashboard_public_artifacts.py -q`
3. `python3 scripts/run_rq_master_36_01.py`
4. `python3 scripts/validate_dashboard_public_artifacts.py`

## Scope exclusions
- Do not add backend APIs, polling, websockets, or UI-triggered runtime actions.
- Do not change system ownership boundaries in architecture authorities.
- Do not weaken existing fail-closed behavior.

## Dependencies
- Existing dashboard publication path in `scripts/refresh_dashboard.sh` and `scripts/validate_dashboard_public_artifacts.py` must remain canonical.
