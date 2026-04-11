# Plan — RQ-MASTER-36-01-PHASE-2-MERGED — 2026-04-11

## Prompt type
BUILD

## Roadmap item
RQ-MASTER-36-01-PHASE-2-MERGED — REALITY_AND_LEARNING

## Objective
Execute three governed real-world cycles (03–05) and emit deterministic recommendation learning artifacts (baseline comparison, recommendation records/outcomes, accuracy, confidence calibration, stuck-loop detection, compact review surface) with explicit evidence bounds and fail-closed gating.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RQ-MASTER-36-01-PHASE-2-MERGED-2026-04-11.md | CREATE | Plan-first compliance for multi-file BUILD scope |
| scripts/run_rq_master_36_01.py | MODIFY | Emit real cycle 03–05 artifacts plus merged learning loop artifacts with evidence-bound confidence and loop detection |
| tests/test_rq_master_36_01.py | MODIFY | Validate required phase-2 merged artifacts and hard-checkpoint publication expectations |
| scripts/refresh_dashboard.sh | MODIFY | Publish compact recommendation review surface artifact to dashboard/public |
| scripts/validate_dashboard_public_artifacts.py | MODIFY | Enforce compact recommendation review artifact presence in public truth surface |
| docs/reviews/RVW-RQ-MASTER-36-01-PHASE-2-MERGED.md | CREATE | Review of reality+learning implementation quality and risks |
| docs/reviews/RQ-MASTER-36-01-PHASE-2-MERGED-DELIVERY-REPORT.md | CREATE | Delivery report with validation evidence and residual gaps |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_rq_master_36_01.py`
2. `python3 scripts/run_rq_master_36_01.py`
3. `python3 scripts/validate_dashboard_public_artifacts.py`

## Scope exclusions
- No schema/manifest version changes.
- No unrelated refactors outside RQ-MASTER-36-01 phase-2 merged execution and publication surfaces.

## Dependencies
- `README.md`
- `docs/architecture/system_registry.md`
- Existing cycle traces in `artifacts/rdx_runs/REAL-WORLD-EXECUTION-CYCLE-01-artifact-trace.json` and `...-02-...` as lineage anchors.
