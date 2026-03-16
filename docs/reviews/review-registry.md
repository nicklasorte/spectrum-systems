# Review Registry

This table is generated from `review-registry.json` and provides a human-readable summary of all design and architecture reviews recorded for `spectrum-systems`. For full metadata (action tracker paths, scope, carried-forward findings) consult the JSON source.

See `docs/reviews/README.md` for the review protocol and `ADR-005-review-protocol.md` for the governance decision.

## Review Table

| Review ID | Date | Type | Repo | Reviewer | Status | Maturity Rating | Follow-up Trigger |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [2026-03-14-architecture-review](2026-03-14-architecture-review.md) | 2026-03-14 | Architecture review | spectrum-systems | Claude (Reasoning Agent) | In Progress | — | When SYS-007/SYS-008/SYS-009 implementation repos begin work; or when first MINOR/MAJOR contract change is proposed |
| [2026-03-14-governance-architecture-review](2026-03-14-governance-architecture-review.md) | 2026-03-14 | Governance architecture review | spectrum-systems | Claude (Reasoning Agent) | Open | — | When GA-001 through GA-003 are completed; or when first implementation repo reaches pilot status |
| [2026-03-15-ecosystem-constitution-audit](2026-03-15-ecosystem-constitution-audit.md) | 2026-03-15 | Ecosystem constitution audit | spectrum-systems | Claude (Principal Systems Architect stance) | Open | 2/5 | When RC-1 (Python package removal) and RC-4 (Phase 1 enforcement) are completed; re-audit for maturity Level 3 |
| [2026-03-15-cross-repo-ecosystem-architecture-review](2026-03-15-cross-repo-ecosystem-architecture-review.md) | 2026-03-15 | Cross-repo ecosystem architecture review | Ecosystem (all 8 repos) | Claude (Principal Systems Architect — cross-repo ecosystem audit) | Open | 2/5 — Structured | When REC-1 through REC-4 are completed; re-audit ecosystem maturity |
| [2026-03-15-governance-architecture-audit](2026-03-15-governance-architecture-audit.md) | 2026-03-15 | Governance architecture audit | spectrum-systems | Claude (Principal Systems Architect — Opus 4.6) | Open | 2.5/5 — Structured, approaching Governed | When A-1 (production code removal) is completed; when A-3 (Phase 1 enforcement) is operational |
| [2026-03-16-operational-ai-systems-roadmap-review](2026-03-16-operational-ai-systems-roadmap-review.md) | 2026-03-16 | Systems architecture review of strategic roadmap | spectrum-systems | Claude (Principal Systems Architect — Opus 4.6) | Open | — | When RM-001 through RM-003 are completed; or when first Layer 2 system begins design |
| [2026-03-16-governance-constitution-deep-review](2026-03-16-governance-constitution-deep-review.md) | 2026-03-16 | Deep governance and constitutional architecture review | spectrum-systems | Claude (Principal Systems Architect — Governance Constitutional Review) | Open | 2/5 — Structured (approaching Governed) | When A-1 (governance-declaration.template.json) is merged and Phase 1 transitions to Active; when boundary CI (A-3) flags spectrum_systems/ |

## Carried-Forward Findings (as of 2026-03-16)

The following findings from prior reviews remain unresolved and are tracked in the `2026-03-16-governance-constitution-deep-review` registry entry. See `review-registry.json` for full `carried_forward_findings` detail.

| Finding ID | Source Review | Description | Status |
| --- | --- | --- | --- |
| RC-1 | 2026-03-15-ecosystem-constitution-audit | Production Python package (`spectrum_systems/study_runner/`) and `run_study.py` violate the architecture boundary. Currently designated an evaluation scaffold pending relocation. | Open |
| RC-2 | 2026-03-15-ecosystem-constitution-audit | Artifact boundary CI enforces data artifact rules only; does not flag implementation code. | Open |
| GA-007 | 2026-03-14-governance-architecture-review | `contracts/governance-declaration.template.json` did not exist; no machine-readable format for governance declarations. | Resolved (2026-03-16) |
| GA-008 | 2026-03-14-governance-architecture-review | Production implementation code in `spectrum_systems/` constitutes a self-governance failure. | Open |
| F-2 | 2026-03-16-governance-constitution-deep-review | Artifact boundary CI does not enforce the implementation code boundary. | Open |

## Notes

- All reviews are recorded in `review-registry.json` (machine-readable source of truth).
- Action trackers for each review are stored in `docs/review-actions/`.
- The review schema is defined in `review-registry.schema.json`.
- Reviews are conducted following the protocol in `CLAUDE_REVIEW_PROTOCOL.md` and `docs/design-review-standard.md`.
- ADR-005 (`docs/adr/ADR-005-review-protocol.md`) documents the governance decision to adopt Claude-led design reviews.
