# DASHBOARD-UI-NEXT-24-SERIAL-02 Review

## 1) Summary of what changed
- Repaired Phase 0 trust blockers first: render gate is now exclusive in `RepoDashboard`, and blocked states only show `BlockedState`, minimal truth strip, and explicitly labeled non-operational debug/provenance details.
- Extended the centralized loader to retrieve recommendation artifacts (`next_action_recommendation_record.json`) and conditionally load `recommendation_accuracy_tracker.json` when manifest-declared.
- Strengthened runtime validation with discriminator-aware checks for critical artifacts.
- Reworked render-state guard logic to derive completeness from manifest-declared artifacts and prioritize `source_not_live` before stale checks.
- Updated selector contracts for manifest-content-derived integrity fields, truthful recommendation provenance, and explicit explorer coverage distinctions.
- Added/extended contract tests for all blocker invariants requested in Hard Checkpoint 0.

## 2) File/module map
- `dashboard/components/RepoDashboard.tsx`
- `dashboard/components/sections/DashboardSections.tsx`
- `dashboard/lib/loaders/dashboard_publication_loader.ts`
- `dashboard/lib/validation/dashboard_validation.ts`
- `dashboard/lib/guards/render_state_guards.ts`
- `dashboard/lib/selectors/dashboard_selectors.ts`
- `dashboard/types/dashboard.ts`
- `dashboard/tests/dashboard_contracts.test.js`
- `docs/review-actions/PLAN-DASHBOARD-UI-NEXT-24-SERIAL-02-2026-04-11.md`

## 3) New/updated render-state and view-model contracts
- `DashboardViewModel.integrity` now includes `declaredCount`, `loadedCount`, and `validLoadedCount`.
- `manifestCompleteness` is now derived from declared vs loaded+valid artifact coverage.
- `syncAuditState` is now manifest-content-derived (`manifest:<publication_state>`).
- Recommendation contract now carries:
  - `provenance` rows used directly by the drawer
  - `synthesizedFallback` boolean marker when recommendation is not artifact-backed.
- Explorer contract now uses explicit `ExplorerCoverageStatus` values:
  - `declared_loaded_valid`
  - `declared_not_loaded`
  - `declared_missing`
  - `loaded_invalid`
  - `loaded_undeclared`

## 4) Validation coverage added
- Added discriminator checks:
  - `repo_snapshot_meta.json`: requires `data_source_state`, `last_refreshed_time`
  - `hard_gate_status_record.json`: requires `readiness_status`
  - `current_run_state_record.json`: requires `current_run_status`
- Added recommendation shape check:
  - `next_action_recommendation_record.json`: requires `records` array.

## 5) Review-blocker fixes completed
- ✅ Exclusive top-level render gate enforced.
- ✅ Dead `runtime_hotspots` triple-null stub removed.
- ✅ Blocked states no longer render operational dashboard sections.
- ✅ Recommendation now loads from artifact record (with explicit synthesized fallback marker only when unavailable/invalid).
- ✅ Manifest completeness and sync audit now derive from manifest content.
- ✅ Guard order prioritizes `source_not_live` before stale.
- ✅ Validation is discriminator-aware for critical artifacts.
- ✅ Recommendation provenance drawer now points to actual recommendation provenance.
- ✅ Explorer now distinguishes declared-loaded/not-loaded/missing/invalid states.

## 6) Provenance coverage and artifact coverage improvements
- Recommendation provenance now maps to `source_basis` from recommendation records when available.
- Provenance drawer for recommendation now uses `model.recommendation.provenance` instead of hard gate defaults.
- Publication integrity section now displays declared/loaded/valid counts to avoid implied complete coverage.

## 7) Test coverage added
Added test assertions for:
- Exclusive blocked-state gate.
- Non-rendering of operational surfaces in blocked states.
- Manifest-derived completeness/sync logic presence.
- Recommendation loader coverage.
- Critical discriminator validation logic.
- Truthful recommendation provenance drawer binding.
- Explorer status distinctions.

## 8) Route rendering strategy and why
- Route strategy unchanged in this batch (homepage remains dynamic; executive summary remains split route).
- This batch focused on fail-closed render integrity and trust-surface correctness, consistent with checkpoint ordering.

## 9) Remaining gaps
- Most tests are contract/structure-level assertions and should be supplemented by behavior-level selector/guard unit tests with executable fixtures.
- `hard_gate_status_record.json` and `current_run_state_record.json` sample artifacts currently lack the discriminator fields now required; this is correctly fail-closed but may require producer alignment.
- Deep operator surfaces from later phases (topology/comparison/hotspots scorecards enhancements) remain to be advanced in later checkpoints.

## 10) Recommended next hard gate
Proceed to **HARD CHECKPOINT 1** with mandatory additions:
1. Behavior-level tests for `deriveRenderState` and `selectDashboardViewModel` with fixture matrices.
2. Section-level unavailable/partial state contract tests.
3. Loader authority checks proving no nested artifact reads before renderability gate.
