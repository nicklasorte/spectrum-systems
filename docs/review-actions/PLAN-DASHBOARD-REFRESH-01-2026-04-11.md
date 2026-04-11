# PLAN — DASHBOARD-REFRESH-01

- **Prompt Type:** PLAN
- **Batch:** DASHBOARD-REFRESH-01
- **Umbrella:** REPO_OBSERVABILITY_LAYER
- **Date:** 2026-04-11

## Scope
Deliver a deterministic local execution workflow that refreshes the repository snapshot artifact, stages it for dashboard consumption, emits refresh metadata, and supports optional local watch-based refresh without introducing backend services.

## Execution Steps
1. Add `scripts/refresh_dashboard.sh` to run the existing snapshot generator, write `artifacts/dashboard/repo_snapshot.json`, copy it to `dashboard/public/repo_snapshot.json`, and emit `dashboard/public/repo_snapshot_meta.json` with refresh timestamp, source path, and byte size.
2. Add `scripts/run_dashboard.sh` to execute refresh first, enforce dashboard directory and dependency presence, then start the dashboard app for local development.
3. Add `scripts/watch_dashboard.py` using Python standard library polling with include/exclude rules, mtime snapshot diffing, and debounce to rerun refresh only when relevant repo files change.
4. Create review and delivery documents in `docs/reviews/` covering fail-closed behavior, optional watch-mode posture, contract preservation, and v1 boundaries.
5. Run validation commands and record outcomes, including expected fail-closed handling where repository surfaces are absent.

## Failure Rules
- Refresh execution fails closed if snapshot generator is missing, dashboard directory is missing, copy/metadata write fails, or generator execution fails.
- Watch mode logs refresh failure and continues watching without silent suppression.
- Existing dashboard snapshot is not replaced when generation fails.

## Out of Scope
- No backend APIs, websockets, database state, or browser push plumbing.
- No file-indexing framework or third-party watch dependencies.
- No unrelated refactors outside dashboard refresh execution tooling.
