# Plan — TLS-STACK-03B — 2026-04-26

## Prompt type
BUILD

## Roadmap item
TLS-STACK-03

## Objective
Resolve System Registry Guard protected-authority and shadow-ownership violations by removing owner-shaped phrasing from HOP requested-candidate explanations while preserving ranking semantics.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/tls_dependency_graph/ranking.py | MODIFY | Replace protected ownership/authority phrasing in HOP explanation with observer-safe non-owning language. |
| tests/tls_dependency_graph/test_phase4_ranking.py | MODIFY | Update assertion to verify HOP explanation communicates non-bypass semantics without protected authority phrasing. |
| artifacts/system_dependency_priority_report.json | MODIFY | Refresh generated artifact after explanation text change. |
| artifacts/tls/system_dependency_priority_report.json | MODIFY | Refresh phase artifact after explanation text change. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS`
2. `pytest tests/tls_dependency_graph/test_phase4_ranking.py`
3. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
4. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
5. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`

## Scope exclusions
- Do not alter scoring, sorting, or top-5 ranking semantics.
- Do not add dashboard-side ranking or control logic.
- Do not introduce fallback/silent recovery behavior.

## Dependencies
- Prior TLS-STACK-03 implementation remains baseline; this is a bounded guard-compliance correction.
