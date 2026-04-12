# Plan — DASHBOARD-UI-FIX-TRUTH-INTEGRITY-01 — 2026-04-11

## Prompt type
BUILD

## Roadmap item
DASHBOARD-UI-FIX-TRUTH-INTEGRITY-01

## Objective
Apply surgical trust-integrity remediations for dashboard selectors, validation, provenance, sync semantics, and render-gated operational reads while preserving fail-closed render suppression.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DASHBOARD-UI-FIX-TRUTH-INTEGRITY-01-2026-04-11.md | CREATE | Required written plan before multi-file BUILD updates. |
| dashboard/types/dashboard.ts | MODIFY | Add typed sync-audit artifact and explicit status enums used by selector mapping. |
| dashboard/lib/loaders/dashboard_publication_loader.ts | MODIFY | Load sync-audit artifact and include it in publication/allArtifacts set. |
| dashboard/lib/validation/dashboard_validation.ts | MODIFY | Enforce discriminator-aware type/enum checks for critical artifacts and fail closed on malformed payloads. |
| dashboard/lib/selectors/dashboard_selectors.ts | MODIFY | Remove token heuristics, use enum mapping/fallback labeling, artifact-first recommendation provenance, truthful sync semantics, and real keysUsed entries. |
| dashboard/components/RepoDashboard.tsx | MODIFY | Remove ungated operational pre-read (`runtime_hotspots`) from top-level branch. |
| dashboard/tests/dashboard_contracts.test.js | MODIFY | Add regression checks for heuristic removal, stronger validation, provenance truth, recommendation artifact-first/fallback labeling, and sync-audit sourcing. |

## Tests that must pass after execution
1. `pytest`
2. `cd dashboard && npm test`
3. `cd dashboard && npm run build`

## Scope exclusions
- No new UI features.
- No layout/styling changes.
- No broad refactors or surface expansion.
