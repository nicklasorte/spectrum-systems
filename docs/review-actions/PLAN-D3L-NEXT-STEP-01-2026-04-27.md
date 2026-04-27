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
| scripts/build_next_step_decision.py | CREATE | Thin CLI for deterministic next-step artifact build |
| scripts/build_dashboard_3ls_with_tls.py | MODIFY | Integrate next-step build + fail-closed checks + skip flag |
| spectrum_systems/modules/runtime/next_step/__init__.py | CREATE | Module package surface |
| spectrum_systems/modules/runtime/next_step/next_step_inputs.py | CREATE | Source loading + hashing + status extraction |
| spectrum_systems/modules/runtime/next_step/next_step_dependency_rules.py | CREATE | Locked dependency/gating logic |
| spectrum_systems/modules/runtime/next_step/next_step_redteam.py | CREATE | Deterministic red-team sequencing checks |
| spectrum_systems/modules/runtime/next_step/next_step_artifact.py | CREATE | Artifact shape construction + validation |
| spectrum_systems/modules/runtime/next_step/next_step_engine.py | CREATE | Orchestration and next-step selection |
| tests/test_next_step_decision.py | MODIFY | Add coverage for new runtime next-step decision builder |
| tests/test_build_dashboard_3ls_with_tls.py | MODIFY | Verify wrapper next-step integration and skip behavior |
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
1. `python scripts/build_next_step_decision.py`
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

## Dependencies
- Existing TLS build wrapper remains canonical and is extended, not bypassed.
- Source-of-truth precedence remains aligned with docs/roadmaps/system_roadmap.md and contracts/examples/system_roadmap.json.
