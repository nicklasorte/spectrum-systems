# Plan — D3L-NEXT-STEP-01 — 2026-04-27

## Prompt type
PLAN

## Roadmap item
D3L-NEXT-STEP-01

## Objective
Implement deterministic background next-step recommendation artifact generation, wire it into the 3LS dashboard build path, and render the artifact in a read-only dashboard panel.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-D3L-NEXT-STEP-01-2026-04-27.md | CREATE | Required written plan for >2 file BUILD scope |
| scripts/build_next_step_recommendation.py | CREATE | Thin CLI for deterministic next-step artifact build |
| scripts/build_dashboard_3ls_with_tls.py | MODIFY | Integrate next-step build + fail-closed checks + skip flag |
| spectrum_systems/modules/dashboard_3ls/next_step_recommendation/* | CREATE | Recommendation module package |
| tests/test_next_step_recommendation.py | CREATE | Coverage for recommendation builder |
| tests/test_build_dashboard_3ls_with_tls.py | MODIFY | Verify wrapper recommendation integration |
| apps/dashboard-3ls/lib/nextStepArtifactLoader.ts | CREATE | Artifact loader for dashboard/API |
| apps/dashboard-3ls/app/api/next-step/route.ts | CREATE | Read-only API route exposing artifact payload |
| apps/dashboard-3ls/components/NextStepPanel.tsx | CREATE | Read-only UI panel for next-step recommendation |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Fetch/render next-step panel |
| apps/dashboard-3ls/__tests__/lib/nextStepArtifactLoader.test.ts | CREATE | Loader tests |
| apps/dashboard-3ls/__tests__/components/NextStepPanel.test.tsx | CREATE | Panel rendering tests |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Validate integration rendering |
| docs/reviews/D3L-NEXT-STEP-01-DELIVERY-REPORT.md | CREATE | Final delivery report requested by prompt |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/build_next_step_recommendation.py`
2. `python -m pytest tests/ -q -k "next_step or dashboard_3ls or build_dashboard"`
3. `npm --prefix apps/dashboard-3ls test -- --runInBand`
4. `npm --prefix apps/dashboard-3ls run build`
5. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
6. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
7. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`

## Scope exclusions
- Do not add live model calls.
- Do not add browser-side ranking or dashboard-side recommendation computation.
- Do not start or implement RFX LOOP-09/10 execution work.
- Do not mutate unrelated governance or contract surfaces.
