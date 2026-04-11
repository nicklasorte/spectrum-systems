# Plan — DASHBOARD-UI-NEXT-24-01 — 2026-04-11

## Prompt type
BUILD

## Roadmap item
DASHBOARD-UI-NEXT-24-01

## Objective
Refactor the dashboard into modular artifact loader/validation/selector/presentation layers with explicit fail-closed render states, provenance visibility, and operator/executive mode split.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| dashboard/app/page.tsx | MODIFY | Keep dynamic route behavior and wire server-side view-model resolution. |
| dashboard/app/executive-summary/page.tsx | CREATE | Add explicit executive summary route split from operator surface. |
| dashboard/components/RepoDashboard.tsx | MODIFY | Reduce to composed modular section host. |
| dashboard/components/primitives/* | CREATE | Add reusable governed UI primitives. |
| dashboard/components/sections/* | CREATE | Add typed section renderers with explicit state wrappers. |
| dashboard/components/drawers/* | CREATE | Add provenance drill-down drawer surfaces. |
| dashboard/components/topology/* | CREATE | Add operator topology panel and derived node status rendering. |
| dashboard/components/review/* | CREATE | Add review queue/checkpoint surface. |
| dashboard/lib/loaders/fetch_json_artifact.ts | CREATE | Centralized artifact fetch and parse behavior. |
| dashboard/lib/loaders/dashboard_publication_loader.ts | CREATE | Centralized publication artifact loader with existence and validation flow. |
| dashboard/lib/validation/* | CREATE | Runtime validation at UI boundary. |
| dashboard/lib/selectors/* | CREATE | View-model derivation and section selectors. |
| dashboard/lib/guards/* | CREATE | Fail-closed guard helpers and render-state gates. |
| dashboard/types/dashboard.ts | CREATE | Typed contracts including discriminated render states and section inputs. |
| dashboard/tests/* | CREATE | Loader, selector, and render-state contract tests. |
| dashboard/package.json | MODIFY | Add test dependencies and scripts. |
| dashboard/vitest.config.ts | CREATE | Test runner configuration. |
| dashboard/tsconfig.json | MODIFY | Include test typing support if needed. |
| docs/reviews/dashboard_ui_next_24_01_review.md | CREATE | Structured delivery review artifact required by the prompt. |

## Contracts touched
None.

## Tests that must pass after execution
1. `cd dashboard && npm run build`
2. `cd dashboard && npm run test`
3. `cd dashboard && npm run lint`

## Scope exclusions
- Do not redesign governed artifact semantics or replace fail-closed behavior.
- Do not introduce synthetic fallback snapshot content.
- Do not remove homepage `force-dynamic` route behavior.

## Dependencies
- Current dashboard publication artifacts in `dashboard/public/` remain the data source.
