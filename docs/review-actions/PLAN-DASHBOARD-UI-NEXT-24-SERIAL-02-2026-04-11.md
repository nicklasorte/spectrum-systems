# Plan — DASHBOARD-UI-NEXT-24-SERIAL-02 — 2026-04-11

## Prompt type
PLAN

## Roadmap item
DASHBOARD-UI-NEXT-24-SERIAL-02

## Objective
Repair render-integrity trust failures first, then advance governed dashboard surfaces with artifact-first loader, validation, render gating, and provenance-correct view-model contracts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DASHBOARD-UI-NEXT-24-SERIAL-02-2026-04-11.md | CREATE | Required written plan before multi-file BUILD updates. |
| docs/reviews/dashboard_ui_next_24_serial_02_review.md | CREATE | Delivery report covering blocker fixes, contracts, tests, and remaining gaps. |
| dashboard/types/dashboard.ts | MODIFY | Extend publication/view-model types for recommendation artifacts, manifest coverage states, and provenance metadata. |
| dashboard/lib/loaders/dashboard_publication_loader.ts | MODIFY | Centralize retrieval of manifest-declared recommendation and integrity artifacts. |
| dashboard/lib/validation/dashboard_validation.ts | MODIFY | Add discriminator-aware validation for critical artifacts and recommendation artifacts. |
| dashboard/lib/guards/render_state_guards.ts | MODIFY | Enforce fail-closed render-state ordering so truth violations are not masked by stale. |
| dashboard/lib/selectors/dashboard_selectors.ts | MODIFY | Ground completeness and sync state in manifest content; bind recommendation and provenance to driving artifacts; classify explorer coverage truthfully. |
| dashboard/components/RepoDashboard.tsx | MODIFY | Make blocked-state render gate exclusive and limit blocked-state UI to non-operational surfaces. |
| dashboard/components/sections/DashboardSections.tsx | MODIFY | Ensure recommendation provenance uses recommendation provenance data and explorer reflects declared/loaded distinction. |
| dashboard/tests/dashboard_contracts.test.js | MODIFY | Add regression tests for render-gate exclusivity, manifest-derived integrity, artifact-backed recommendation loading, discriminator validation, truthful provenance, and explorer distinctions. |

## Contracts touched
None.

## Tests that must pass after execution
1. `cd dashboard && npm test`
2. `cd dashboard && npm run build`

## Scope exclusions
- Do not redesign unrelated routes or global app shell.
- Do not weaken fail-closed behavior for visual convenience.
- Do not introduce synthetic artifact fallbacks that imply verified coverage.

## Dependencies
- NEXT-24-01 architecture review findings are treated as blocking prerequisites and repaired first in this execution.
