# PLAN — TLS-NEXT-01-2026-04-27

## Prompt type
`BUILD`

## Scope
Integrate TLS artifacts into dashboard system graph signals so artifact-backed execution dominates, stub fallback is non-primary, and fail-closed reasons are explicit.

## Files in scope
| Path | Action | Notes |
| --- | --- | --- |
| `scripts/tls_next_01_integration.py` | CREATE | Deterministic integration builder for TLS graph, validation, red-team, and roadmap artifacts. |
| `apps/dashboard-3ls/app/api/health/route.ts` | MODIFY | Read TLS integration artifact and use stub fallback only when system artifact data is missing. |
| `apps/dashboard-3ls/lib/artifactLoader.ts` | MODIFY | Add typed loaders for TLS phase artifacts and integration payloads. |
| `apps/dashboard-3ls/__tests__/api/health.test.ts` | MODIFY | Assert fail-closed and source behavior for integration-backed health response. |
| `tests/test_tls_next_01_integration.py` | CREATE | Deterministic tests for source mix dominance, repo registry coverage, graph validation, lineage/replay fields, and red-team outputs. |

## Deterministic execution steps
1. Implement a deterministic integration builder that ingests TLS-01..04 artifacts plus canonical system registry and emits integration + validation + red-team + roadmap artifacts.
2. Emit fail-closed policy_observation logic: missing required artifacts or incomplete graph must produce FREEZE reasons and non-zero script exit.
3. Wire dashboard health route to consume integration artifact as primary system graph source; allow stub fallback only per-system when no artifact row exists.
4. Add tests for script outputs and dashboard source behavior.
5. Run focused test commands for changed surfaces.

## Out of scope
- No changes to ranking logic generation in TLS-04.
- No dashboard-side recomputation of ranking order.
- No cross-module runtime authority changes outside dashboard/read-only integration surfaces.
