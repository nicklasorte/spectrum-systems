# Plan — TLS-STACK-03 — 2026-04-26

## Prompt type
BUILD

## Roadmap item
TLS-STACK-03

## Objective
Harden requested candidate ranking explanations and dependency justification signals while preserving global TLS ranking semantics and keeping dashboard behavior artifact-read-only.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/tls_dependency_graph/ranking.py | MODIFY | Add explanation fields and deterministic observer-safe explanation synthesis for requested candidate rows. |
| schemas/artifacts/system_dependency_priority_report.schema.json | MODIFY | Extend requested candidate row schema with required explanation and warning fields. |
| artifacts/system_dependency_priority_report.json | MODIFY | Regenerate TLS priority artifact with new requested candidate explanation fields. |
| apps/dashboard-3ls/lib/artifactLoader.ts | MODIFY | Extend dashboard artifact types and shape contract for new requested candidate fields. |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Render expandable requested candidate explanation details without computing ranking. |
| tests/tls_dependency_graph/test_phase4_ranking.py | MODIFY | Add ranking explanation tests and authority-vocabulary guard assertions. |
| apps/dashboard-3ls/__tests__/lib/artifactLoaderPriority.test.ts | MODIFY | Validate loader compatibility with expanded requested candidate row shape. |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Verify dashboard rendering of requested candidate explanation details. |

## Contracts touched
- `schemas/artifacts/system_dependency_priority_report.schema.json` (requested candidate row shape extension; schema version unchanged)

## Tests that must pass after execution
1. `python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS`
2. `pytest tests/tls_dependency_graph`
3. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
4. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
5. `cd apps/dashboard-3ls && npm test -- --runTestsByPath __tests__/lib/artifactLoaderPriority.test.ts __tests__/components/DashboardPage.test.tsx`

## Scope exclusions
- Do not change TLS global ranking score/order semantics or top-5 computation logic.
- Do not make dashboard compute ranking or derive candidate ordering.
- Do not introduce owner-shaped authority vocabulary in new requested-candidate explanation fields.

## Dependencies
- TLS-STACK-02 requested candidate ranking baseline must remain intact.
