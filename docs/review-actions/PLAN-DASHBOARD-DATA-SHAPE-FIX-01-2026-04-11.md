# Plan — DASHBOARD-DATA-SHAPE-FIX-01 — 2026-04-11

## Prompt type
PLAN

## Roadmap item
REPO_OBSERVABILITY_LAYER

## Objective
Align dashboard snapshot typing and rendering to the emitted `repo_snapshot.json` artifact contract without changing layout, loading model, or backend behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| dashboard/components/RepoDashboard.tsx | MODIFY | Correct snapshot data types, fallback shape, and object-list rendering for hotspots/signals. |
| docs/reviews/RVW-DASHBOARD-DATA-SHAPE-FIX-01.md | CREATE | Record required review answers and verdict for this batch. |
| docs/reviews/DASHBOARD-DATA-SHAPE-FIX-01-DELIVERY-REPORT.md | CREATE | Record delivery outcomes and validation evidence. |

## Contracts touched
None.

## Tests that must pass after execution
1. `cd dashboard && npm install`
2. `cd dashboard && npm run build`

## Scope exclusions
- Do not redesign dashboard layout or panel structure.
- Do not add dependencies or backend/API services.
- Do not change fetch artifact paths or loading behavior.
- Do not modify non-dashboard runtime/governance logic.

## Dependencies
None.
