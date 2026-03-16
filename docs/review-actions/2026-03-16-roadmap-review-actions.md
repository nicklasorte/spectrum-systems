# Architecture Review Action Tracker — Operational AI Systems Roadmap

- **Source Review:** `docs/reviews/2026-03-16-operational-ai-systems-roadmap-review.md`
- **Owner:** TBD
- **Last Updated:** 2026-03-16

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RM-001 | Register all roadmap systems (SYS-010–SYS-020) in systems registry; create BN-007–BN-012 in bottleneck map | TBD | Open | None | 6 new Layer 1 systems + 5 Layer 2 systems + Spectrum Intelligence Map need registry entries |
| RM-002 | Write canonical ID standard (`docs/canonical-id-standard.md`) defining ID format, namespace, uniqueness scope, and resolution | TBD | Open | None | Blocks reliable cross-engine artifact linking; prerequisite for Layer 2 development |
| RM-003 | Revise dependency ladder: move Knowledge Capture Engine to Phase 1, Spectrum Study Operating System to Phase 3, add infrastructure gate | TBD | Open | None | Current sequence has dependency violations (consumers built before producers) |
| RM-004 | Define canonical knowledge model schemas (decision-record, assumption-record, memory-object) in spectrum-systems | TBD | Open | RM-002 | Prevents three independent knowledge stores with incompatible schemas |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RM-005 | Write boundary documents for three overlapping system pairs: (a) Stress Test / Review Prediction, (b) Knowledge Capture / Institutional Memory, (c) Program Advisor / Autopilot | TBD | Open | RM-001 | Each pair needs exclusive artifact ownership and handoff specification |
| RM-006 | Elevate ontology to active governance work; write `docs/ontology-standard.md` with initial spectrum domain term set | TBD | Open | None | Currently Tier 4 in data lake strategy but practically required for Layer 2 |
| RM-007 | Define infrastructure gate between Layer 1 and Layer 2 with testable readiness criteria | TBD | Open | RM-002, RM-003 | Gate requires: canonical IDs, cross-engine contracts, artifact store readiness, ontology baseline |
| RM-008 | Write schema design standard enforcing common fields, naming conventions, versioning rules | TBD | Open | None | Prevents schema fragmentation across 15+ engines |
| RM-014 | Evaluate artifact store requirements; stabilize external artifact manifest (carries forward GA-004) | TBD | Open | None | 15+ systems need governed artifact storage; manifest contract needs stabilization |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RM-009 | Resolve naming inconsistencies between roadmap and systems registry; document canonical names with aliases | TBD | Open | RM-001 | Meeting Intelligence System ↔ Meeting Minutes Engine; Working Paper Stress Test ↔ SYS-007 relationship |
| RM-010 | Write simulation interface standard (`docs/simulation-interface-standard.md`) | TBD | Open | None | Required before Interference Analysis Assistant or Regulatory Impact Simulator |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RM-011 | Add cross-cutting concerns section to roadmap (observability, auditability, security) | TBD | Open | None | 100-step roadmap covers these but operational AI roadmap does not |
| RM-012 | Write Layer 2 integration standard (`docs/layer-2-integration-standard.md`) | TBD | Open | RM-007 | Defines composition, event handling, failure modes for multi-engine consumers |
| RM-013 | Evaluate whether Review Prediction Engine and Spectrum Study Autopilot justify standalone repos | TBD | Open | RM-005 | May be capabilities within existing repos; record decision in ADR |

## Blocking Items
- **RM-002 (Canonical ID Standard)** blocks cross-engine artifact linking. Must be resolved before any Layer 2 system begins development.
- **RM-004 (Canonical Knowledge Model)** blocks Knowledge Capture Engine and Institutional Memory Engine from being built with consistent schemas.
- **GA-004 (External Artifact Manifest Stabilization)** from prior reviews remains unresolved and blocks artifact flow infrastructure. Carried forward as dependency of RM-014.

## Deferred Items
- **RM-013 (Repo merge evaluation for Review Prediction Engine / Autopilot)** — Defer until Working Paper Stress Test and Spectrum Study Program Advisor reach "Design complete" status.
- **Spectrum Intelligence Map detailed architecture review** — Defer until at least 3 Layer 1 engines produce stable, contract-governed outputs (estimated: completion of Phase 2 in revised build sequence).
