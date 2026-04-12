# Plan — DASHBOARD-REFRESH-PUBLISH-LOOP-01 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
DASHBOARD-REFRESH-PUBLISH-LOOP-01

## Objective
Implement a governed refresh, freshness-validation, publication-gating, and operator diagnostic execution loop for dashboard publication artifacts with fail-closed behavior and trace-linked artifact outputs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/dashboard_freshness_contract.schema.json | CREATE | Canonical freshness contract schema. |
| contracts/schemas/refresh_run_record.schema.json | CREATE | Governed refresh-run trace artifact schema. |
| contracts/schemas/dashboard_freshness_status_record.schema.json | CREATE | Governed per-artifact freshness verdict schema. |
| contracts/schemas/publication_attempt_record.schema.json | CREATE | Governed publish-decision artifact schema. |
| contracts/examples/dashboard_freshness_contract.json | CREATE | Freshness contract example artifact. |
| contracts/examples/refresh_run_record.json | CREATE | Refresh run example artifact. |
| contracts/examples/dashboard_freshness_status_record.json | CREATE | Freshness status example artifact. |
| contracts/examples/publication_attempt_record.json | CREATE | Publication attempt example artifact. |
| contracts/standards-manifest.json | MODIFY | Register new governed contract artifacts and version bump. |
| dashboard/types/dashboard.ts | MODIFY | Typed contract models for refresh/freshness/publication artifacts. |
| dashboard/lib/validation/dashboard_validation.ts | MODIFY | Harden freshness/publication validators and reason-code checks. |
| dashboard/lib/loaders/dashboard_publication_loader.ts | MODIFY | Load new refresh/publication artifacts and fail-closed wiring. |
| dashboard/lib/guards/render_state_guards.ts | MODIFY | Enforce freshness contract truth gates and certification-like gate checks. |
| dashboard/lib/selectors/dashboard_selectors.ts | MODIFY | Add narrow operator support freshness/publish diagnostics. |
| scripts/generate_repo_dashboard_snapshot.py | MODIFY | Emit authoritative UTC freshness timestamp on each refresh run. |
| scripts/dashboard_refresh_publish_loop.py | CREATE | Shared deterministic refresh/publish execution path for scheduled/manual/test modes. |
| scripts/refresh_dashboard.sh | MODIFY | Implement scheduled/manual refresh entrypoints, trace linkage, publication gating, artifacts, and replay-friendly deterministic decisions. |
| scripts/validate_dashboard_public_artifacts.py | MODIFY | Enforce malformed artifact rejection + publish precondition gate checks. |
| dashboard/tests/dashboard_contracts.test.js | MODIFY | Coverage for new validation and gate logic surfaces. |
| dashboard/tests/dashboard_publication_coverage.test.js | MODIFY | Coverage for refresh/load/gate/linkage behavior. |
| tests/test_dashboard_refresh_publish_loop.py | CREATE | Deterministic python tests for refresh/publish artifacts, failure taxonomy, and replay/failure injection. |
| docs/reviews/dashboard_refresh_publish_loop_01_delivery.md | CREATE | Delivery review artifact. |
| docs/reviews/dashboard_refresh_publish_loop_01_red_team.md | CREATE | Mandatory red-team review artifact. |
| docs/reviews/dashboard_refresh_publish_loop_01_fix_handoff.md | CREATE | Surgical blocker/fix handoff artifact. |

## Contracts touched
- New schemas for freshness contract, refresh run record, freshness status record, and publication attempt record.
- standards-manifest version increment + new contract registrations.

## Tests that must pass after execution
1. `pytest tests/test_dashboard_refresh_publish_loop.py tests/test_contracts.py tests/test_contract_enforcement.py`
2. `python scripts/run_contract_enforcement.py`
3. `python scripts/validate_dashboard_public_artifacts.py`
4. `bash scripts/refresh_dashboard.sh`
5. `cd dashboard && npm test -- --runInBand`
6. `cd dashboard && npm run build`

## Scope exclusions
- No unrelated dashboard UI redesign.
- No bypass path for manual refresh.
- No weakening of fail-closed publication gating.
- No refactor of unrelated runtime modules.

## Dependencies
- Canonical source alignment with `README.md` and `docs/architecture/system_registry.md`.
