# Plan — D3L-FINALIZE-01 — 2026-04-28

## Prompt type
BUILD

## Roadmap item
D3L-FINALIZE-01

## Objective
Finalize remaining 3LS dashboard UI correctness and fail-closed behavior, then produce readiness artifacts and validation evidence in one PR.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| artifacts/tls/d3l_finalize_inventory_report.json | CREATE | Capture current implementation coverage, gaps, and risks. |
| artifacts/tls/d3l_finalize_redteam_report.json | CREATE | Record red-team findings and status. |
| artifacts/tls/d3l_finalize_fix_log.json | CREATE | Log fixes applied for red-team findings. |
| artifacts/tls/d3l_final_readiness_packet.json | CREATE | Produce final readiness packet with gating status. |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Enforce overview compactness and ranking fail-closed surfaces. |
| apps/dashboard-3ls/components/SystemTrustGraph.tsx | MODIFY | Enforce clean graph default and mode-specific edge visibility. |
| apps/dashboard-3ls/components/TrustGraphSection.tsx | MODIFY | Wire graph mode behavior and ranking overlay suppression. |
| apps/dashboard-3ls/components/RecommendationDebugPanel.tsx | MODIFY | Suppress actionable recommendations when ranking blocked. |
| apps/dashboard-3ls/components/GraphLegend.tsx | MODIFY | Dark mode/readability and mode warning polish. |
| apps/dashboard-3ls/components/SystemInspector.tsx | MODIFY | Dark mode/readability polish. |
| apps/dashboard-3ls/components/EdgeInspector.tsx | MODIFY | Dark mode/readability polish. |
| apps/dashboard-3ls/components/ActivityLog.tsx | MODIFY | Dark mode/readability polish. |
| apps/dashboard-3ls/lib/systemGraph.ts | MODIFY | Keep graph nodes/edges registry-aligned and mode-filtered. |
| apps/dashboard-3ls/lib/ranking.ts | MODIFY | Canonical ranking freshness/blocked behavior and client-side guard. |
| apps/dashboard-3ls/lib/maturity.ts | MODIFY | Ensure maturity coverage/derivation behavior for active systems. |
| apps/dashboard-3ls/lib/mvpGraph.ts | MODIFY | Keep MVP capability graph separated from 3LS registry nodes. |
| apps/dashboard-3ls/lib/artifactLoader.ts | MODIFY | Canonical ranking blocked reason and freshness parsing. |
| apps/dashboard-3ls/__tests__/page.test.tsx | MODIFY | Cover overview compactness and ranking suppression. |
| apps/dashboard-3ls/__tests__/graph.test.tsx | MODIFY | Cover clean/default graph mode filtering. |
| apps/dashboard-3ls/__tests__/ranking.test.tsx | MODIFY | Cover stale/missing/invalid/fresh ranking behavior. |
| apps/dashboard-3ls/__tests__/mvpGraph.test.ts | MODIFY | Cover MVP separation and registry-only mappings. |
| apps/dashboard-3ls/__tests__/darkMode.test.tsx | MODIFY | Cover key dark mode readability/status semantics. |
| apps/dashboard-3ls/__tests__/ocIntegration.test.tsx | MODIFY | Cover compact OC card behavior when present/missing/stale/conflict. |
| tests/test_d3l_*.py | MODIFY | Align integration expectations for finalized UI/guards if needed. |

## Contracts touched
None.

## Tests that must pass after execution
1. `npm --prefix apps/dashboard-3ls test -- --runInBand`
2. `npm --prefix apps/dashboard-3ls run build`
3. `pytest tests/metrics/test_met_04_18_contract_selection.py tests/metrics/test_met_19_33_contract_selection.py`
4. `pytest tests/test_d3l_*.py`
5. `pytest tests/test_tls_roadmap_artifacts.py tests/test_tls_boundary_map.py`
6. `pytest tests/ -k "dashboard or d3l or tls or maturity or ranking or registry or oc"`
7. `python scripts/validate_system_registry.py`
8. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
9. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
10. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`

## Scope exclusions
- Do not add new systems or non-registry 3LS nodes.
- Do not introduce new architecture beyond D3L finalize behavior.
- Do not weaken fail-closed, registry, authority, or freshness guards.

## Dependencies
- D3L-MASTER-01 and D3L-UI-FIX must already be landed.
