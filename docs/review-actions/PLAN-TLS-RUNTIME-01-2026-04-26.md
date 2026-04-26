# Plan — TLS-RUNTIME-01 — 2026-04-26

## Prompt type
WIRE

## Roadmap item
TLS-RUNTIME-01

## Objective
Ensure TLS dependency-priority artifact generation is enforced during build and deployment so dashboard-3ls consumes a present artifact with fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| package.json | MODIFY | Wire TLS artifact generation/verification into build scripts |
| scripts/build_tls_dependency_priority.py | MODIFY | Add `--fail-if-missing` CLI behavior and fail-closed checks |
| apps/dashboard-3ls/** | MODIFY | Ensure runtime/load path expects generated artifact without fallback ranking compute |
| .vercelignore | MODIFY/CREATE | Ensure `artifacts/` is not ignored for deployment |
| vercel.json | MODIFY (if needed) | Preserve artifact availability in deployment configuration |
| tests/** | MODIFY/CREATE | Add tests for missing-artifact build failure and dashboard artifact load success |

## Contracts touched
None.

## Tests that must pass after execution
1. Targeted tests validating TLS artifact failure mode and dashboard artifact load path.
2. Any relevant build command that now enforces artifact existence.

## Scope exclusions
- Do not add ranking computation logic to dashboard runtime.
- Do not bypass TLS script pipeline with hardcoded data.
- Do not weaken fail-closed behavior for missing artifact.

## Dependencies
- Existing TLS priority generator script and dashboard loader behavior.
