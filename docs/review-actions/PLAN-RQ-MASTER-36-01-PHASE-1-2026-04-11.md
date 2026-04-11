# Plan — RQ-MASTER-36-01-PHASE-1 — 2026-04-11

## Prompt type
BUILD

## Roadmap item
RQ-MASTER-36-01-PHASE-1 — OPERATOR_TRUTH_PUBLICATION

## Objective
Make `dashboard/public/` a deterministic, fail-closed publication surface sourced from governed artifacts with explicit freshness/staleness signaling.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RQ-MASTER-36-01-PHASE-1-2026-04-11.md | CREATE | Plan-first requirement for multi-file BUILD execution |
| scripts/refresh_dashboard.sh | MODIFY | Deterministic, auditable publication sync from governed artifacts with fail-closed completeness gate |
| scripts/validate_dashboard_public_artifacts.py | MODIFY | Enforce required public artifact completeness and fallback/live ambiguity checks |
| tests/test_validate_dashboard_public_artifacts.py | MODIFY | Add validation coverage for freshness and ambiguity guards |
| tests/test_refresh_dashboard_publication.py | CREATE | Deterministic checks for publication sync hardening and fail-closed behavior |
| docs/reviews/RVW-RQ-MASTER-36-01-PHASE-1.md | CREATE | Review output for phase execution and trust guarantees |
| docs/reviews/RQ-MASTER-36-01-PHASE-1-DELIVERY-REPORT.md | CREATE | Delivery report for implementation, validation, and residual risk |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_refresh_dashboard_publication.py`
2. `pytest tests/test_validate_dashboard_public_artifacts.py`
3. `bash scripts/refresh_dashboard.sh`
4. `python3 scripts/validate_dashboard_public_artifacts.py`
5. `cd dashboard && npm run lint`
6. `cd dashboard && npm run build`

## Scope exclusions
- Do not modify dashboard React component behavior beyond publication truth wiring.
- Do not change contract schemas or standards manifest.
- Do not alter unrelated CI workflows or governance modules.

## Dependencies
- Existing governed artifact emitters remain authoritative for `artifacts/rq_master_36_01/` and `artifacts/ops_master_01/`.
