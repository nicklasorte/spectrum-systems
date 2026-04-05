# TPA Trust Boundary Verification Action Tracker — 2026-04-05

- Source Review: docs/reviews/2026-04-05-tpa-trust-boundary-verification.md
- Owner: Spectrum Systems maintainers
- Last Updated: 2026-04-05

## High-Priority Items
| ID | Risk | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- |
| HI-1 | Repeated hardening dampening corroboration is prefix-based and can be satisfied by non-TPA-looking strings without explicit artifact validation at decision time. | Require at least one validated/resolvable non-TPA corroboration artifact before allowing repeated hardening escalation. | Open | Derived from Section 2 + Remaining Risks #2. |

## Medium-Priority Items
| ID | Risk | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- |
| MI-1 | Override expiry enforcement does not explicitly enforce not-before semantics (`issued_at <= enforcement_now`). | Add explicit issuance-bound check in AG-04 override enforcement logic. | Open | Derived from Section 1 caveat + Remaining Risks #1. |
