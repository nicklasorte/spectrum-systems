# Plan — TLS-RUNTIME-01B — 2026-04-26

## Prompt type
WIRE

## Roadmap item
TLS-RUNTIME-01B

## Objective
Diagnose Vercel build failure and make dashboard-3ls TLS build wiring cwd-safe while preserving fail-closed artifact generation and canonical artifact-only runtime loading.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| apps/dashboard-3ls/package.json | MODIFY | Replace brittle relative command with cwd-safe build wrapper invocation |
| scripts/build_dashboard_3ls_with_tls.py | CREATE | Centralize cwd-safe TLS generation + artifact verification + dashboard build handoff |
| tests/test_build_dashboard_3ls_with_tls.py | CREATE | Validate cwd-safe command construction and fail-closed artifact checks |
| docs/review-actions/PLAN-TLS-RUNTIME-01B-2026-04-26.md | CREATE | Required written plan for multi-file WIRE change |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing`
2. `npm --prefix apps/dashboard-3ls run build`
3. `pytest tests/test_build_tls_dependency_priority.py`
4. `pytest tests/test_build_dashboard_3ls_with_tls.py`
5. Guard commands for authority-shape, authority-leak, and system-registry.

## Scope exclusions
- Do not remove TLS artifact generation from dashboard build.
- Do not add dashboard-side ranking computation.
- Do not add silent fallback for missing artifact.
- Do not relax `--fail-if-missing` behavior.

## Dependencies
- Existing TLS pipeline and dashboard artifact loader path (`artifacts/system_dependency_priority_report.json`).
