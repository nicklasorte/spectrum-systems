# PLAN — TLS-NEXT-01-FIX-2026-04-27

## Prompt type
`BUILD`

## Scope
Fix authority-shape preflight wording in TLS-NEXT-01 plan artifact and fix dashboard health card status typing/behavior for upstream `unknown` raw status without weakening fail-closed invariants.

## Files in scope
| Path | Action | Notes |
| --- | --- | --- |
| `docs/review-actions/PLAN-TLS-NEXT-01-2026-04-27.md` | MODIFY | Replace authority-shaped wording that violates reserved authority-cluster ownership. |
| `apps/dashboard-3ls/lib/signalStatus.ts` | MODIFY | Make card-status mapping explicitly handle raw `unknown` status and return card-safe statuses. |
| `apps/dashboard-3ls/app/api/health/route.ts` | MODIFY | Preserve raw status + reason codes while returning card-safe status values. |
| `apps/dashboard-3ls/__tests__/lib/signalStatus.test.ts` | MODIFY | Add unknown-status card mapping assertions and update status expectations. |
| `apps/dashboard-3ls/__tests__/api/health.test.ts` | MODIFY | Assert route preserves raw unknown diagnostic and never surfaces healthy for unknown. |
| `tests/test_authority_shape_preflight.py` | MODIFY | Add regression for non-owner plan doc usage of reserved authority-shaped tokens. |

## Deterministic steps
1. Replace plan wording with lower-authority term (`policy_observation`) that passes authority-shape preflight.
2. Update card-status mapping to accept raw `unknown` and deterministically map to warning/critical by source provenance.
3. Add diagnostics (`raw_status`, `status_reason_codes`) in health response rows.
4. Extend tests for authority-shape and unknown-status mapping.
5. Run authority-shape preflight, dashboard tests/type checks, and targeted TLS integration pytest.
