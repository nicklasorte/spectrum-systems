# BAJ Provenance Hardening Surgical Review — Action Tracker

- **Source Review:** `docs/reviews/2026-03-23-baj-provenance-hardening-surgical-review.md`
- **Owner:** Runtime Governance Working Group
- **Last Updated:** 2026-03-23

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Implement a canonical provenance builder/validator and route enforcement/replay/drift/SK emitters through it. | Runtime Governance WG | Open | Contract alignment across provenance-bearing schemas | Must preserve deterministic IDs and fail-closed behavior. |
| CR-2 | Tighten provenance contract minimums (run_id, trace_id, span_id, generator identity/version, timestamp, source/parent refs where applicable). | Contracts Steward | Open | CR-1 design sign-off | Use additive-compatible schema updates where possible. |
| CR-3 | Remove synthetic SK trace/span fallback and enforce fail-closed on missing trace context. | Strategic Knowledge Module Owner | Open | None | Missing trace context must block decision emission. |
| CR-4 | Decommission or hard-gate legacy `enforce_budget_decision` emission path unless canonical provenance + schema validation are guaranteed. | Runtime Enforcement Owner | Open | CR-1 canonical path | Keep allowlist restrictions until retirement complete. |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Add runtime↔replay provenance parity tests asserting compatible canonical shape. | Test Owner | Open | CR-1 | Include drift attachment and replay-result validation path. |
| HI-2 | Add CI guard to detect provenance-bearing schemas that do not reference canonical provenance shape. | Contracts + CI Owner | Open | CR-2 | Fail PRs that introduce dialect drift. |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Add audit fixture that joins runtime enforcement, replay, drift, and SK decisions to validate lineage continuity. | QA | Open | CR-1, HI-1 | Treat join failures as blocking for release candidate. |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| LI-1 | Document provenance field semantics and mapping examples for governance reviewers. | Docs Owner | Open | CR-2 | Keep examples contract-versioned. |

## Blocking Items
- CR-1 blocks all parity and contract-hardening implementation tasks.
- CR-2 blocks productionization of CI schema drift checks and documentation finalization.

## Deferred Items
- None.
