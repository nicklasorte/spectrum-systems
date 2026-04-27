# Plan — D3L-NEXT-STEP-01B — 2026-04-27

## Prompt type
PLAN

## Roadmap item
D3L-NEXT-STEP-01B

## Objective
Resolve remaining authority-shape vocabulary violations in D3L next-step recommendation surfaces without changing behavior.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-D3L-NEXT-STEP-01B-2026-04-27.md | CREATE | Required written plan for >2 file BUILD scope |
| docs/review-actions/PLAN-D3L-NEXT-STEP-01A-2026-04-27.md | MODIFY | Replace legacy vocabulary tokens |
| spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_dependency_rules.py | MODIFY | Replace reserved wording with safe recommendation wording |
| spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_engine.py | MODIFY | Replace reserved review/approval wording |
| tests/test_next-step-legacy.py equivalent surface | DELETE | Remove stale legacy next-step test file from D3L surface |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_authority_shape_preflight.py --base-ref c09da271dd9cbf948f29afed0c60cf88e08610a6 --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
2. `python scripts/build_next_step_recommendation.py`
3. `python -m pytest tests/ -q -k "next_step or recommendation or dashboard_3ls or build_dashboard"`
4. `npm --prefix apps/dashboard-3ls test -- --runInBand`
5. `npm --prefix apps/dashboard-3ls run build`

## Scope exclusions
- Do not modify authority-shape guard behavior.
- Do not add allow-list exceptions.
- Do not change recommendation behavior.
- Do not alter dashboard recommendation computation boundaries.
