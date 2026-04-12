# Plan — DASHBOARD-UI-FIX-PUBLICATION-COVERAGE-02 — 2026-04-12

## Prompt type
BUILD

## Roadmap item
DASHBOARD-UI-FIX-PUBLICATION-COVERAGE-02

## Objective
Restore dashboard renderability by aligning publication loader artifact coverage and validation semantics with the manifest-required artifact contract while preserving fail-closed gating.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DASHBOARD-UI-FIX-PUBLICATION-COVERAGE-02-2026-04-12.md | CREATE | Required plan-first artifact for multi-file changes |
| dashboard/lib/loaders/dashboard_publication_loader.ts | MODIFY | Build `allArtifacts` from all manifest `required_files` and expose a generic declared-artifact map |
| dashboard/lib/validation/dashboard_validation.ts | MODIFY | Keep strict validators and add safe baseline validation for untyped artifacts |
| dashboard/types/dashboard.ts | MODIFY | Add generic manifest-backed artifact map to publication model |
| dashboard/tests/dashboard_publication_coverage.test.js | MODIFY | Verify manifest-wide coverage, loader behavior, and fail-closed behavior |

## Scope exclusions
- Do not weaken `deriveRenderState` fail-closed behavior.
- Do not reduce manifest `required_files`.
- Do not add fallback snapshots.
- Do not introduce UI feature changes or broad refactors.

## Required verification
1. `pytest`
2. `npm test --prefix dashboard`
3. `npm run build --prefix dashboard`
