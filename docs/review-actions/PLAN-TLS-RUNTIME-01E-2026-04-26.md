# Plan — TLS-RUNTIME-01E — 2026-04-26

## Prompt type
WIRE

## Roadmap item
TLS-RUNTIME-01E

## Objective
Preserve required TLS build inputs in the Vercel bundle and add explicit preflight failure messaging when the registry input is missing before TLS execution.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| .vercelignore | MODIFY | Stop excluding required TLS inputs while keeping ignore scope narrow |
| scripts/build_dashboard_3ls_with_tls.py | MODIFY | Add preflight existence check for docs/architecture/system_registry.md with actionable failure output |
| tests/test_build_dashboard_3ls_with_tls.py | MODIFY | Cover missing-registry preflight failure behavior |
| docs/review-actions/PLAN-TLS-RUNTIME-01E-2026-04-26.md | CREATE | Required plan for multi-file WIRE change |

## Contracts touched
None.

## Tests that must pass after execution
1. `npm --prefix apps/dashboard-3ls run build`
2. `python scripts/build_dashboard_3ls_with_tls.py --skip-next-build`
3. `pytest tests/test_build_tls_dependency_priority.py`
4. `pytest tests/test_build_dashboard_3ls_with_tls.py`

## Scope exclusions
- Do not relax fail-closed behavior.
- Do not make registry parsing optional.
- Do not add fallback registry inputs.
- Do not add dashboard-side ranking logic.

## Dependencies
- TLS parser requirement on `docs/architecture/system_registry.md`.
