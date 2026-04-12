# Plan — DASHBOARD-UI-FIX-PUBLICATION-COVERAGE-01 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
DASHBOARD-UI-FIX-PUBLICATION-COVERAGE-01

## Objective
Restore dashboard renderability by making the publication loader cover all manifest-declared required artifacts while preserving fail-closed render gating.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DASHBOARD-UI-FIX-PUBLICATION-COVERAGE-01-2026-04-12.md | CREATE | Required pre-execution plan for multi-file surgical change |
| dashboard/lib/loaders/dashboard_publication_loader.ts | MODIFY | Load all manifest-declared required artifacts and align allArtifacts coverage |
| dashboard/lib/validation/dashboard_validation.ts | MODIFY | Add lightweight validation for newly loaded artifacts that lack strict validators |
| dashboard/tests/dashboard_publication_coverage.test.js | CREATE | Add regression tests for loader coverage and render gate behavior |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest`
2. `npm test --prefix dashboard`
3. `npm run build --prefix dashboard`

## Scope exclusions
- Do not weaken `deriveRenderState` fail-closed behavior.
- Do not implement recommendation-policy fallback changes.
- Do not redesign dashboard UI/operator surfaces.
- Do not broad-refactor dashboard types/selectors beyond coverage alignment.

## Dependencies
- None.
