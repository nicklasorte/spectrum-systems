# Plan — D3L-SIMPLE-TLS-01 — 2026-04-27

## Prompt type
BUILD

## Roadmap item
D3L-SIMPLE-TLS-01

## Objective
Simplify `apps/dashboard-3ls` into a tabbed operator cockpit with an overview constrained to trust pulse, artifact-backed flowchart, top-3 TLS recommendations, and roadmap-backed leverage queue.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-D3L-SIMPLE-TLS-01-2026-04-27.md | CREATE | Required plan-first artifact for multi-file dashboard change. |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Replace overloaded single-page view with tabbed cockpit and simplified overview. |
| apps/dashboard-3ls/lib/dashboardSimplified.ts | CREATE | Add artifact-only helper logic for top-3 extraction and roadmap queue grouping. |
| apps/dashboard-3ls/app/api/tls-roadmap/route.ts | CREATE | Provide fail-closed API surface for TLS roadmap artifacts and rendered table source. |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Validate overview scope, tab isolation, artifact-backed top-3/queue logic, and fail-closed warnings. |
| apps/dashboard-3ls/__tests__/components/Met03Panels.test.tsx | MODIFY | Align MET-03 dashboard assertions with simplified cockpit scope. |
| apps/dashboard-3ls/__tests__/api/met-01-02-seed-loop.test.ts | MODIFY | Relax brittle string checks while preserving seed/fallback wiring coverage. |
| apps/dashboard-3ls/__tests__/api/system-graph.test.ts | MODIFY | Keep edge-integrity assertions while allowing optional validation warning presence. |
| artifacts/tls/d3l_simple_dashboard_redteam_report.json | CREATE | Record red-team findings for simplified dashboard operator clarity checks. |
| artifacts/tls/d3l_simple_dashboard_fix_log.json | CREATE | Record fixes applied from red-team findings. |

## Contracts touched
None.

## Tests that must pass after execution

1. `npm --prefix apps/dashboard-3ls test -- --runInBand`
2. `npm --prefix apps/dashboard-3ls run build`
3. `pytest tests/test_tls_roadmap_artifacts.py`
4. `authority_shape_preflight`
5. `authority_leak_guard`
6. `system_registry_guard`

## Scope exclusions

- Do not add new TLS intelligence, ranking logic, or dashboard-side re-ranking.
- Do not implement control loops, learning loops, or execution authority behavior.
- Do not modify canonical architecture ownership definitions.

## Dependencies

- `artifacts/system_dependency_priority_report.json` present and schema-valid.
- `artifacts/tls/tls_roadmap_final.json` and `artifacts/tls/tls_roadmap_table.md` present for queue/roadmap display.
