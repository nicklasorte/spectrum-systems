# Plan — DASHBOARD-FIX-NULL-RENDER-01 — 2026-04-11

## Prompt type
PLAN

## Roadmap item
DASHBOARD-FIX-NULL-RENDER-01

## Objective
Eliminate homepage null-dereference during Next.js prerender/build and enforce explicit fail-closed render gating via typed publication load states.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DASHBOARD-FIX-NULL-RENDER-01-2026-04-11.md | CREATE | Required plan before multi-file dashboard/build hardening. |
| dashboard/app/page.tsx | MODIFY | Encode explicit route rendering strategy and page boundary wrapper. |
| dashboard/components/RepoDashboard.tsx | MODIFY | Add discriminated load-state union and renderability gate; remove nullable deref paths. |
| tests/test_dashboard_render_gate_contract.py | CREATE | Add regression checks for render-gate state model and route strategy contract. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_dashboard_render_gate_contract.py`
2. `cd dashboard && npm run build`
3. `pytest tests/test_validate_dashboard_public_artifacts.py tests/test_refresh_dashboard_publication.py tests/test_rq_next_24_01.py`

## Scope exclusions
- Do not reintroduce fallback snapshot behavior.
- Do not alter publication contract schemas.
- Do not refactor unrelated dashboard sections outside null/render gate hardening.

## Dependencies
- Prior publication integrity and truth-validation flow in `scripts/refresh_dashboard.sh` and `scripts/validate_dashboard_public_artifacts.py` remains authoritative.
