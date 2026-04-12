# DASHBOARD-REFRESH-PUBLISH-LOOP-01 Delivery

## Summary of changes
- Implemented a governed refresh/publish execution loop (`scripts/dashboard_refresh_publish_loop.py`) used by `scripts/refresh_dashboard.sh` for scheduled/manual/test modes.
- Added canonical freshness/publish contracts and examples for: freshness contract, refresh run record, freshness status record, publication attempt record.
- Strengthened public artifact validation to block malformed freshness/publication artifacts and require trace linkage.
- Extended dashboard loader/validation/guards/selectors/types to consume refresh/publication artifacts and enforce fail-closed render behavior.
- Added deterministic tests for refresh/publish behavior, failure injection, and mode parity.

## Module/file map
- Contracts: `contracts/schemas/*.schema.json`, `contracts/examples/*.json`, `contracts/standards-manifest.json`
- Runtime scripts: `scripts/generate_repo_dashboard_snapshot.py`, `scripts/dashboard_refresh_publish_loop.py`, `scripts/refresh_dashboard.sh`, `scripts/validate_dashboard_public_artifacts.py`
- Dashboard runtime: `dashboard/lib/loaders/dashboard_publication_loader.ts`, `dashboard/lib/validation/dashboard_validation.ts`, `dashboard/lib/guards/render_state_guards.ts`, `dashboard/lib/selectors/dashboard_selectors.ts`, `dashboard/types/dashboard.ts`
- Tests: `tests/test_dashboard_refresh_publish_loop.py`, `dashboard/tests/dashboard_contracts.test.js`, `dashboard/tests/dashboard_publication_coverage.test.js`

## Schemas added
- `dashboard_freshness_contract`
- `refresh_run_record`
- `dashboard_freshness_status_record`
- `publication_attempt_record`

## Artifacts added/emitted
- `dashboard/public/refresh_run_record.json`
- `dashboard/public/publication_attempt_record.json`
- `artifacts/rq_master_36_01/dashboard_freshness_status_record.json`
- `artifacts/rq_master_36_01/dashboard_refresh_publish_metrics.json`
- `artifacts/rq_master_36_01/dashboard_refresh_publish_alert.json`

## Code paths changed
- Refresh path now enforces explicit precondition gates and writes refresh/publication decision artifacts before publication.
- Publish is blocked/frozen when freshness, manifest coherence, required files, or trace linkage fail.
- Dashboard render guard now blocks on `publication_attempt_record.decision != allow` and trace mismatch.

## Tests added
- Deterministic mode parity and failure injection tests in `tests/test_dashboard_refresh_publish_loop.py`.
- Dashboard unit tests expanded for new loader/guard/validator seams.

## Threshold/contract decisions
- Authoritative freshness source: `repo_snapshot.json.generated_at`
- Freshness threshold: `21600s` (6h)
- Freshness contract version: `1.0.0`
- Publish decision semantics: `allow | block | freeze`

## Remaining gaps
- Error-budget policy uses existing `error_budget_enforcement_outcome.json` status; richer budget-burn math is a follow-up hardening item.
- Scheduler is implemented as mode parity in the same entrypoint; cron/workflow binding remains deployment-level wiring.
