# D3L-NEXT-STEP-01 Delivery Report

## Prompt type
BUILD

## What runs in background
The 3LS dashboard build wrapper now runs deterministic recommendation generation in-process as part of repository build automation:

1. `scripts/build_dashboard_3ls_with_tls.py`
2. `scripts/build_tls_dependency_priority.py`
3. `scripts/build_next_step_recommendation.py`
4. Next.js build

No model calls, no browser-side ranking, and no runtime daemons are introduced.

## Artifact path
- `artifacts/next_step_recommendation_report.json`

## Dashboard path
- API: `apps/dashboard-3ls/app/api/next-step/route.ts`
- UI: `apps/dashboard-3ls/components/NextStepPanel.tsx` rendered from `apps/dashboard-3ls/app/page.tsx`

## Source inputs
The recommendation builder loads and hashes these evidence artifacts:

- `contracts/examples/system_roadmap.json`
- `docs/roadmaps/system_roadmap.md`
- `docs/roadmaps/rfx_cross_system_roadmap.md`
- `artifacts/system_dependency_priority_report.json`
- `artifacts/rmp_01_delivery_report.json`
- `artifacts/rmp_drift_report.json`
- `artifacts/blf_01_baseline_failure_fix/delivery_report.json`
- `contracts/review_artifact/H01_review.json` (if present)
- `docs/reviews/H01_pre_mvp_spine_review.md` (if present)
- `artifacts/rfx_04_loop_07_08/delivery_report.json` (if present)
- Optional H01 final/fix-plan artifacts, when present

## Fail-closed behavior
- Missing required inputs return blocked output with `reason_codes` and fail the builder script non-zero.
- Dashboard API never fabricates recommendations; missing artifact returns blocked payload.
- Build wrapper requires artifact existence after next-step builder unless `--skip-next-step` is explicitly provided.

## Tests run
- `python scripts/build_next_step_recommendation.py`
- `python -m pytest tests/ -q -k "next_step or dashboard_3ls or build_dashboard"`
- `npm --prefix apps/dashboard-3ls test -- --runInBand`
- `npm --prefix apps/dashboard-3ls run build`
- `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
- `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
- `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`

## Remaining limitations
- Recommendation logic currently relies on declared artifact status/readiness fields and deterministic lock-order rules; it does not perform deep semantic proof validation beyond red-team consistency checks.
