# Plan — DASHBOARD-NEXT-24-01 — 2026-04-11

## Prompt type
PLAN

## Roadmap item
DASHBOARD-NEXT-24-01

## Objective
Upgrade the dashboard publication and rendering flow to artifact-first, fail-closed execution with explicit truth enforcement and canonical system-map projection.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DASHBOARD-NEXT-24-01-2026-04-11.md | CREATE | Required written plan before multi-file BUILD execution. |
| scripts/refresh_dashboard.sh | MODIFY | Enforce publication integrity, manifest completeness/checksum, and fail-closed atomic publication metadata. |
| scripts/validate_dashboard_public_artifacts.py | MODIFY | Enforce no-fallback truth policy, manifest/file completeness matching, and truth-violation fail-close gates. |
| dashboard/components/RepoDashboard.tsx | MODIFY | Remove fallback snapshot behavior, centralize data retrieval, explicit no-data degradation, truth violation detection, and operator system map. |
| tests/test_validate_dashboard_public_artifacts.py | MODIFY | Add deterministic validation coverage for no-fallback and publication manifest truth enforcement. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_validate_dashboard_public_artifacts.py`
2. `pytest tests/test_refresh_dashboard_publication.py`
3. `pytest tests/test_rq_next_24_01.py`

## Scope exclusions
- Do not modify unrelated governance roadmaps or architecture registries.
- Do not change contract schemas in `contracts/schemas/`.
- Do not refactor unrelated dashboard styling or non-dashboard modules.

## Dependencies
- Canonical runtime rules from `README.md` and `docs/architecture/system_registry.md` remain authoritative during implementation.
