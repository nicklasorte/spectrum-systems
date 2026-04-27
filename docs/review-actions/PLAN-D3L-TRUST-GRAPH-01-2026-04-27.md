# Plan — D3L-TRUST-GRAPH-01 — 2026-04-27

## Prompt type
BUILD

## Roadmap item
D3L-TRUST-GRAPH-01

## Objective
Upgrade dashboard-3ls to render an artifact-backed trust-aware system graph with explicit recompute flow, fail-closed artifact handling, and investigative/freeze explanation surfaces.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| apps/dashboard-3ls/app/api/system-graph/route.ts | CREATE | Add normalized graph API over governed artifacts with explicit missing/degraded states. |
| apps/dashboard-3ls/app/api/recompute-graph/route.ts | CREATE | Add controlled recompute endpoint with fail-closed execution reporting. |
| apps/dashboard-3ls/lib/systemGraph.ts | CREATE | Define normalized trust graph payload contracts shared by API and UI. |
| apps/dashboard-3ls/lib/systemGraphBuilder.ts | CREATE | Build normalized graph payload from artifacts without route-coupled runtime dependencies. |
| apps/dashboard-3ls/components/TrustPulseBar.tsx | CREATE | Display trust posture, artifact coverage, recompute timing, and warnings. |
| apps/dashboard-3ls/components/SystemTrustGraph.tsx | CREATE | Render trust-aware graph section, focus/dimming, inspector integration, and activity log. |
| apps/dashboard-3ls/components/SystemNode.tsx | CREATE | Encapsulate node rendering for trust/source/warning state. |
| apps/dashboard-3ls/components/SystemEdge.tsx | CREATE | Encapsulate edge rendering by confidence/type/failure state. |
| apps/dashboard-3ls/components/SystemInspector.tsx | CREATE | Add investigate mode panel for selected system evidence/dependencies. |
| apps/dashboard-3ls/components/ExplainFreezePanel.tsx | CREATE | Show freeze/degraded explanation from artifact evidence only. |
| apps/dashboard-3ls/components/RecomputeGraphButton.tsx | CREATE | Trigger recompute API and preserve last-known artifact visibility. |
| apps/dashboard-3ls/components/ActivityLog.tsx | CREATE | Track local graph/recompute/operator interactions. |
| apps/dashboard-3ls/components/TrustGraphSection.tsx | CREATE | Orchestrate graph fetch, recompute state, and section layout. |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Wire trust graph section near top while preserving existing panels. |
| apps/dashboard-3ls/__tests__/api/system-graph.test.ts | CREATE | Validate graph API payload and missing-artifact warning behavior. |
| apps/dashboard-3ls/__tests__/components/SystemTrustGraph.test.tsx | CREATE | Validate rendering, focus/dimming, inspector, and freeze explanation behaviors. |
| apps/dashboard-3ls/__tests__/components/RecomputeGraphButton.test.tsx | CREATE | Validate recompute success/failure handling and fail-closed UI behavior. |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Update fetch sequence and keep compatibility assertions with new graph section. |
| PLANS.md | MODIFY | Register active plan entry. |

## Contracts touched
None.

## Tests that must pass after execution
1. `npm --prefix apps/dashboard-3ls test -- --runInBand`
2. `npm --prefix apps/dashboard-3ls run build`
3. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
4. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
5. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`

## Scope exclusions
- Do not modify canonical ownership definitions.
- Do not compute ranking in dashboard code.
- Do not hard-code graph relationships as authoritative data.
- Do not introduce D3 or React Flow dependencies.

## Dependencies
- Artifact availability under `artifacts/tls` and `artifacts/system_dependency_priority_report.json`.
