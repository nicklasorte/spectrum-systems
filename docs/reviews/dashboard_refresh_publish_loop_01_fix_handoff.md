# DASHBOARD-REFRESH-PUBLISH-LOOP-01 Surgical Fix Handoff

## Prompt type
BUILD

## Scope
Implement only the blocker fixes from red-team review:
1. Add `publication_bundle_envelope` contract + artifact that signs `dashboard_publication_manifest.json` and `publication_attempt_record.json` hashes.
2. Enforce schema+semantic validation for `error_budget_enforcement_outcome` before freeze/allow decision usage.
3. Add contract pin artifact in dashboard/public asserting freshness threshold and authoritative timestamp field at publish time.
4. Add trace provenance signature field validation to refresh/freshness/publication records.
5. Add deterministic failure-injection regression that tampers staged manifest hashes and verifies fail-closed block.

## Constraints
- No UI expansion.
- No new bypass path.
- Keep shared execution path for scheduled/manual/test.
- Must preserve fail-closed behavior.

## Required checks
- `pytest tests/test_dashboard_refresh_publish_loop.py tests/test_contracts.py tests/test_contract_enforcement.py`
- `python3 scripts/validate_dashboard_public_artifacts.py`
- `bash scripts/refresh_dashboard.sh manual`
