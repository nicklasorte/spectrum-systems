# Plan — D3L-GRAPH-CLEANUP-01 — 2026-04-28

## Prompt type
BUILD

## Roadmap item
D3L-GRAPH-CLEANUP-01

## Objective
Make the Graph tab default to a clean, readable structure view with dense dependency edges available only in explicit diagnostic mode, and move high-noise diagnostic panels out of Overview.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| apps/dashboard-3ls/lib/systemGraph.ts | MODIFY | Define explicit graph modes and labels for selector/UI behavior. |
| apps/dashboard-3ls/components/DebugModeSelector.tsx | MODIFY | Retitle/reuse selector for explicit graph modes. |
| apps/dashboard-3ls/components/SystemTrustGraph.tsx | MODIFY | Enforce edge-render policy by mode (clean default, failure path, selected node, full registry). |
| apps/dashboard-3ls/components/TrustGraphSection.tsx | MODIFY | Default to clean mode, remove dense preview behavior, and apply dark-mode-safe classes. |
| apps/dashboard-3ls/components/GraphLegend.tsx | MODIFY | Align legend with new mode semantics and dark-mode-safe styling. |
| apps/dashboard-3ls/components/SystemInspector.tsx | MODIFY | Apply dark-mode-safe styling for readability. |
| apps/dashboard-3ls/components/EdgeInspector.tsx | MODIFY | Apply dark-mode-safe styling for readability. |
| apps/dashboard-3ls/components/ActivityLog.tsx | MODIFY | Apply dark-mode-safe styling for readability. |
| apps/dashboard-3ls/components/RecommendationDebugPanel.tsx | MODIFY | Apply dark-mode-safe styling for readability. |
| apps/dashboard-3ls/components/SystemTrustStatusCard.tsx | MODIFY | Apply dark-mode-safe styling for readability/warnings. |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Remove specified diagnostic panels from Overview and keep in Diagnostics/Raw only; dark-mode-safe panel classes. |
| apps/dashboard-3ls/__tests__/components/SystemTrustGraph.test.tsx | MODIFY | Add/adjust tests for edge visibility by mode. |
| apps/dashboard-3ls/__tests__/components/TrustGraphSection.test.tsx | MODIFY | Add/adjust tests for default clean mode, mobile clean canvas behavior, and no dense thumbnail defaults. |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Assert removed diagnostics are not on Overview. |

## Contracts touched
None.

## Tests that must pass after execution
1. `npm --prefix apps/dashboard-3ls test -- --runInBand`
2. `npm --prefix apps/dashboard-3ls run build`
3. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
4. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
5. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`

## Scope exclusions
- Do not modify ranking extraction or ordering logic.
- Do not invent new systems or ownership sets.
- Do not remove or weaken registry validation or fail-closed behavior.
- Do not broaden unrelated tabs beyond panel relocation and readability fixes.
