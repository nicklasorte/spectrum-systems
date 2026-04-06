# PQX Architecture Review Action Tracker — 2026-04-05

- Source Review: docs/reviews/2026-04-05-pqx-architecture-review.md
- Owner: Spectrum Systems maintainers
- Last Updated: 2026-04-05

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Enforce strict done-certification defaults for governed PQX execution profile (`require_system_readiness=true`, `allow_warn_as_pass=false`) | Governance + Runtime | Open | Policy version bump + compatibility plan | Addresses permissive default governance seam |
| CR-2 | Add strict proof-closure mode that rejects synthetic fallback refs for eval/control/enforcement/replay evidence in authoritative spine runs | Runtime | Open | Contract/schema update for strict mode selector | Prevents “proof closure without hard evidence” |
| CR-3 | Prevent `unknown_pending_execution` (commit-range inspection allow) from being accepted by execution admission paths | Runtime | Open | Integration tests for inspection vs execution boundaries | Closes preflight-to-execution fail-open seam |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Introduce an explicit, versioned strict-governance profile artifact consumed by sequence runner + done certification | Governance + Runtime | Open | Policy contract + loader wiring | Removes caller-by-caller implicit strictness |
| HI-2 | Add integration tests asserting inspection-mode allowances cannot authorize governed execution | Runtime | Open | None | Boundary hardening test coverage |
| HI-3 | Add closure-integrity metric (real refs vs synthetic refs) and block promotion below threshold | Runtime + Governance | Open | Metric schema + gate consumption | Makes proof quality machine-enforceable |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Add observability counters for warn-grade certifications and policy override frequency across PQX entrypoints | Runtime | Open | None | Detects silent drift toward permissive posture |
| MI-2 | Track synthesized audit markers as a first-class risk signal in bundle/run summaries | Runtime | Open | None | Supports long-term trust monitoring |

## Blocking Items
- CR-1, CR-2, and CR-3 should be treated as blocking for “trust-by-default” claims that PQX is the canonical governed execution spine without caveats.

## Deferred Items
- None.
