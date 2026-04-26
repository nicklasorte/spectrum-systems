# Plan — TLS-STACK-02 — 2026-04-26

## Prompt type
BUILD

## Roadmap item
TLS-STACK-02

## Objective
Add an optional requested candidate-set ranking view to TLS dependency priority artifacts and dashboard without changing global ranking behavior.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| scripts/build_tls_dependency_priority.py | MODIFY | Add --candidates CLI input and pass candidate set into ranking artifact generation. |
| spectrum_systems/modules/tls_dependency_graph/ranking.py | MODIFY | Add requested candidate ranking section while preserving existing global ranking semantics. |
| schemas/artifacts/system_dependency_priority_report.schema.json | MODIFY | Extend schema for requested candidate section and ambiguity rows. |
| artifacts/system_dependency_priority_report.json | MODIFY | Refresh generated artifact with requested candidate fields from CLI run. |
| apps/dashboard-3ls/lib/artifactLoader.ts | MODIFY | Extend loader types/shape guard for requested candidate ranking payload. |
| apps/dashboard-3ls/app/page.tsx | MODIFY | Render requested candidate ranking section and empty-state guidance. |
| tests/tls_dependency_graph/test_phase4_ranking.py | MODIFY | Add deterministic tests for requested candidate ranking behavior and global ranking invariance. |
| tests/tls_dependency_graph/test_phase2_classification.py | MODIFY | Add candidate classification assertions for H01/RFX/HOP/MET/METS behavior. |
| apps/dashboard-3ls/__tests__/lib/artifactLoaderPriority.test.ts | MODIFY | Validate loader support for requested candidate fields and shape guards. |
| apps/dashboard-3ls/__tests__/components/DashboardPage.test.tsx | MODIFY | Verify dashboard rendering for requested ranking and missing candidate set states. |

## Contracts touched
- `schemas/artifacts/system_dependency_priority_report.schema.json` (shape extension only, version unchanged)

## Tests that must pass after execution
1. `python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS`
2. `pytest tests/tls_dependency_graph`
3. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
4. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
5. `cd apps/dashboard-3ls && npm test -- --runTestsByPath __tests__/lib/artifactLoaderPriority.test.ts __tests__/components/DashboardPage.test.tsx`

## Scope exclusions
- Do not alter TLS phase ordering or remove existing global ranking fields.
- Do not introduce canonical owner authority actions/values.
- Do not change unrelated dashboard sections or APIs beyond requested ranking display wiring.

## Dependencies
- Existing TLS-STACK-01 ranking pipeline and dashboard priority loader must remain deterministic.
