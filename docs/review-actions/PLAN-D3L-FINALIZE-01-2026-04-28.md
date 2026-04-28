# Plan — D3L-FINALIZE-01 — 2026-04-28

## Prompt type
BUILD

## Roadmap item
D3L-FINALIZE-01

## Objective
Finalize the 3LS dashboard UI behavior and fail-closed guards, then publish readiness artifacts proving compact overview, ranking suppression, clean default graph, MVP separation, dark-mode readability, and diagnostics compatibility.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Enforce compact overview, canonical rankingBlocked behavior, OC compact unavailable handling, prioritization gating consistency, dark-mode polish for key sections. |
| apps/dashboard-3ls/components/TrustGraphSection.tsx | MODIFY | Add explicit graph mode control and pass mode/ranking gate to graph/debug panel. |
| apps/dashboard-3ls/components/SystemTrustGraph.tsx | MODIFY | Implement clean_structure default and mode-specific edge/node visibility. |
| apps/dashboard-3ls/components/RecommendationDebugPanel.tsx | MODIFY | Enforce fail-closed recommendation suppression from canonical ranking gate. |
| apps/dashboard-3ls/components/GraphLegend.tsx | MODIFY | Add graph-mode warning cue and dark-mode readability polish. |
| apps/dashboard-3ls/components/SystemInspector.tsx | MODIFY | Dark-mode readability + status semantic preservation. |
| apps/dashboard-3ls/components/EdgeInspector.tsx | MODIFY | Dark-mode readability polish. |
| apps/dashboard-3ls/components/ActivityLog.tsx | MODIFY | Dark-mode readability polish. |
| apps/dashboard-3ls/__tests__/components/SystemTrustGraph.test.tsx | MODIFY | Add graph mode coverage (default clean, failure path, selected node, full registry). |
| apps/dashboard-3ls/__tests__/components/TrustGraphSection.test.tsx | MODIFY | Validate graph mode default and ranking suppression propagation to graph debug. |
| apps/dashboard-3ls/__tests__/components/OperatorComplexityBudget.test.tsx | MODIFY | Extend overview/priority/OC compact fail-closed checks. |
| artifacts/tls/d3l_finalize_inventory_report.json | CREATE | Required phase-1 inventory report. |
| artifacts/tls/d3l_finalize_redteam_report.json | CREATE | Required red-team report. |
| artifacts/tls/d3l_finalize_fix_log.json | CREATE | Required fix log for red-team findings. |
| artifacts/tls/d3l_final_readiness_packet.json | CREATE | Required final readiness packet. |

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
- Do not add any new system IDs or non-registry nodes.
- Do not change registry authority ownership definitions.
- Do not introduce client-side ranking computation.
- Do not remove legacy diagnostics anchors required by tests.

## Dependencies
- D3L-MASTER-01 and D3L-UI-FIX must remain intact as baseline behavior.
