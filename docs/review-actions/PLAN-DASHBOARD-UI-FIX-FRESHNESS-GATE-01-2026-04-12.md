# Plan — DASHBOARD-UI-FIX-FRESHNESS-GATE-01 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
DASHBOARD-UI-FIX-FRESHNESS-GATE-01

## Objective
Make dashboard render freshness gating derive from the authoritative publication freshness artifact with explicit fail-closed timestamp validation and threshold contract.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| dashboard/types/dashboard.ts | MODIFY | Add explicit freshness-status artifact types to make freshness contract explicit. |
| dashboard/lib/loaders/dashboard_publication_loader.ts | MODIFY | Load dashboard_freshness_status artifact into publication model. |
| dashboard/lib/guards/render_state_guards.ts | MODIFY | Route stale gate through explicit freshness contract and strict parse checks. |
| dashboard/lib/selectors/dashboard_selectors.ts | MODIFY | Display freshness from authoritative artifact and align note/last refresh fields. |
| dashboard/tests/dashboard_contracts.test.js | MODIFY | Assert explicit freshness contract wiring and fail-closed stale gate behavior. |
| dashboard/tests/dashboard_publication_coverage.test.js | MODIFY | Assert loader and guard freshness-source coverage contract. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest`
2. `cd dashboard && npm test`
3. `cd dashboard && npm run build`

## Scope exclusions
- Do not weaken fail-closed behavior.
- Do not add fallback snapshot behavior.
- Do not change unrelated gating logic.
- Do not add new UI features.

## Dependencies
- None.
