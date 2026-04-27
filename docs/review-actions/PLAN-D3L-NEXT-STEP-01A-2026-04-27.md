# Plan — D3L-NEXT-STEP-01A — 2026-04-27

## Prompt type
PLAN

## Roadmap item
D3L-NEXT-STEP-01A

## Objective
Repair D3L next-step delivery by shifting D3L-owned vocabulary to recommendation terms and moving the builder import path to a Vercel-safe lightweight package.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-D3L-NEXT-STEP-01A-2026-04-27.md | CREATE | Required written plan for >2 file BUILD scope |
| scripts/build_next_step_recommendation.py | CREATE | Recommendation-named, build-safe CLI |
| scripts/build_dashboard_3ls_with_tls.py | MODIFY | Invoke recommendation builder + artifact check |
| spectrum_systems/modules/runtime/next_step/* | DELETE | Remove runtime import boundary |
| spectrum_systems/modules/dashboard_3ls/__init__.py | CREATE | New package root |
| spectrum_systems/modules/dashboard_3ls/next_step_recommendation/* | CREATE | Build-safe stdlib recommendation engine |
| tests/test_next_step_recommendation.py | CREATE | Recommendation behavior + import-safety tests |
| tests/test_build_dashboard_3ls_with_tls.py | MODIFY | Wrapper invocation order assertions |
| apps/dashboard-3ls/lib/nextStepArtifactLoader.ts | MODIFY | Recommendation artifact path + fields |
| apps/dashboard-3ls/app/api/next-step/route.ts | MODIFY | Read-only recommendation payload route |
| apps/dashboard-3ls/components/NextStepPanel.tsx | MODIFY | Render selected_recommendation |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Keep panel integration |
| apps/dashboard-3ls/__tests__/lib/nextStepArtifactLoader.test.ts | MODIFY | Loader expectations updated |
| apps/dashboard-3ls/__tests__/components/NextStepPanel.test.tsx | MODIFY | Panel field expectations updated |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Integration payload shape updated |
| artifacts/next_step_recommendation_report.json | CREATE | Recommendation artifact output |
| docs/review-actions/PLAN-D3L-NEXT-STEP-01-2026-04-27.md | MODIFY | Align references with recommendation naming |
| docs/reviews/D3L-NEXT-STEP-01-DELIVERY-REPORT.md | MODIFY | Align paths and vocabulary |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/build_next_step_recommendation.py`
2. `python -m pytest tests/ -q -k "next_step or recommendation or dashboard_3ls or build_dashboard"`
3. `npm --prefix apps/dashboard-3ls test -- --runInBand`
4. `npm --prefix apps/dashboard-3ls run build`
5. `python scripts/run_authority_shape_preflight.py --base-ref 23112c1aba722045ca29dc06c6ea1124a2e49c58 --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`

## Scope exclusions
- Do not weaken authority-shape checks.
- Do not add allow-list exceptions.
- Do not add silent fallbacks.
- Do not make dashboard compute recommendations.
- Do not install jsonschema as the primary fix.
