# PQX Red-Team Security Audit Action Tracker

- **Source Review:** `docs/reviews/2026-04-02-pqx-red-team-security-audit.md`
- **Owner:** Spectrum Systems maintainers
- **Last Updated:** 2026-04-02

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Fix trace invariant bypass: enforce wrapper_ref presence on blocked slices in `_validate_trace_invariants` | Runtime | Open | None | V-1 BLOCKER |
| CR-2 | Replace substring-based fixture mode resolution with explicit `fixture_decision_mode` parameter in `run_pqx_slice` | Runtime | Open | None | V-2 BLOCKER |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Accept optional timestamp in `enforce_control_decision` to support deterministic replay verification | Runtime | Open | None | V-3 MEDIUM |
| HI-2 | Decouple row completion state from slice runner; mark complete only after enforcement confirms ALLOW | Runtime | Open | None | V-4 MEDIUM |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Fail closed on missing run_id in `_derive_run_id` instead of falling back to trace_id | Runtime | Open | None | V-5 LOW |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |

## Blocking Items
- CR-1 and CR-2 must be resolved before the system can claim audit-grade trace provenance and deterministic execution.

## Deferred Items
- None.
