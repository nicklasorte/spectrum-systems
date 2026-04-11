# PLAN — DASHBOARD-AUTOLOAD-01

- **Prompt Type:** PLAN
- **Batch:** DASHBOARD-AUTOLOAD-01
- **Umbrella:** REPO_OBSERVABILITY_LAYER
- **Date:** 2026-04-10

## Scope
Harden the live repository dashboard component so it auto-loads the generated snapshot from `/artifacts/dashboard/repo_snapshot.json`, preserves fallback behavior with `exampleSnapshot`, and keeps manual textarea editing with explicit source-state visibility.

## Execution Steps
1. Update the React dashboard component (`SpectrumSystemsRepoDashboard`) to attempt `fetch('/artifacts/dashboard/repo_snapshot.json')` on initial render.
2. Add state for snapshot source mode, snapshot text, and optional load status messaging while preserving parse-error handling and manual textarea workflow.
3. Keep `exampleSnapshot` as the fallback contract example and use it when auto-load is absent or invalid.
4. Add compact UI copy indicating one of: auto-loaded snapshot, manual / pasted snapshot, or fallback example snapshot.
5. Create `docs/reviews/RVW-DASHBOARD-AUTOLOAD-01.md` with required review answers and verdict.
6. Create `docs/reviews/DASHBOARD-AUTOLOAD-01-DELIVERY-REPORT.md` with changed files and delivery details.

## Failure Rules
- Fail closed to fallback example when auto-load fetch fails or returned JSON is invalid.
- Do not crash the dashboard on load/parse errors.
- Preserve textarea content on manual parse failure and keep parse-error visibility.

## Out of Scope
- No dashboard redesign.
- No backend/API expansion or external dependencies.
- No snapshot contract changes.
- No unrelated refactors.
