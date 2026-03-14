# Architecture Decision Records (ADRs)

Architecture decisions are captured as ADRs to document irreversible choices, the context that shaped them, and the expected consequences. This keeps spectrum systems governance transparent, reproducible, and easy to audit across the czar ecosystem.

## Relationship to design reviews
- Design reviews (see `docs/design-review-standard.md`) explore options, risks, and recommendations.
- ADRs capture the final decision derived from those reviews and provide the canonical reference for downstream systems.
- Each ADR should cite the design review(s) that informed it and note alignment with the standards manifest and schemas.

## How to add a new ADR
1. Copy `adr-template.md` into this directory as `ADR-XXX-descriptive-slug.md` (use zero-padded numbers).
2. Fill in every section with concise, testable statements; set `Status` to `Proposed` until accepted through governance.
3. Link to the motivating design review, relevant schemas/contracts, and any affected workflows.
4. Update the list of ADRs below to include the new file and its status.

## ADR index
- `ADR-001-czar-repo-org.md` — Accepted — Repo responsibilities for system-factory → spectrum-systems → operational engines
