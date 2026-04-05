# TPA Architecture Review Action Tracker — 2026-04-05

- **Source Review:** `docs/reviews/2026-04-05-tpa-architecture-review.md`
- **Owner:** Spectrum Systems maintainers
- **Last Updated:** 2026-04-05

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Bypass-drift signal dead-end — control bypass risk unmitigated | Critical | Wire TPA bypass drift into control-loop readiness observability (R3) | Open | Blocks strategy alignment |
| CR-2 | TPA scope policy not anchored to source-authority layer — strategy drift | Critical | Anchor `tpa_scope_policy` to source-authority layer with refresh trigger (R5) | Open | Blocks strategy alignment |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Policy surface sprawl — ambiguous precedence across scope/complexity/review/cleanup-only policies | High | Create `tpa_policy_composition` contract with schema + precedence rules (R1) | Open | |
| HI-2 | Certification bypass risk for cleanup-only slices | High | Define unified TPA certification envelope consumed by promotion/done gates (R4) | Open | |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Observability orphan — summary artifact with no declared consumer | Medium | Declare `tpa_observability_summary` consumer contract (R2) | Open | |
| MI-2 | Complexity budget calibration drift | Medium | Document complexity-budget recalibration cadence + review trigger (R6) | Open | |
| MI-3 | Schema bypass risk via lightweight mode | Medium | Add schema-backed allowlist for lightweight-mode evidence drop (R7) | Open | |

## Low-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| LI-1 | — | — | — | — | None at this time |

## Blocking Items
- **B1:** CR-1 and CR-2 block TPA strategy alignment and any TPA maturity-level advancement until resolved.

## Deferred Items
- **D1:** Roadmap prioritizer consumption of TPA observability — triggered by MI-1 completion.
- **D2:** Cross-repo TPA pattern propagation — triggered by HI-1 merge + one full control-loop cycle.
