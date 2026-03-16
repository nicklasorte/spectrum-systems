# Decisions

## Decision 1: Documentation-first design repository
- Context: This repository serves as a lab notebook for automation systems.
- Decision: Maintain a documentation-first approach focused on architecture, workflows, and schemas.
- Rationale: Clarity and traceability are required before any implementation work begins elsewhere.
- Implications: Production code is deferred to downstream implementation repositories.

## Decision 2: Implementation systems live in separate repositories
- Context: Designs produced here will eventually guide build-out work.
- Decision: Keep implementation artifacts outside this repository.
- Rationale: Separating design from implementation preserves flexibility and keeps this notebook focused.
- Implications: Future build tasks reference this repository but ship in dedicated codebases.

## Decision 3: All structured data must follow the provenance standard
- Context: Automation outputs and schemas need consistent trust signals.
- Decision: Apply the data provenance standard defined in docs/data-provenance-standard.md to all structured data.
- Rationale: Provenance ensures traceability, auditability, and reuse across systems.
- Implications: New schemas and artifacts must declare sources, derivations, versions, and review status.

## Decision 4: Automation systems should produce structured artifacts
- Context: Systems target repeatable spectrum engineering workflows.
- Decision: Require systems to emit structured artifacts aligned to schemas and data classes.
- Rationale: Structured outputs enable validation, reuse, and downstream automation.
- Implications: Workflow definitions must specify artifacts, schemas, and validation methods.

## Decision 5: Production-code boundary resolution for spectrum_systems/
- Context: The `spectrum_systems/` Python package was introduced as an evaluation scaffold for contract loading and study-runner prototype work. Reviews from 2026-03-14 through 2026-03-16 (RC-1, A-1, GA-008, F-3) flagged it as a boundary violation inconsistent with the documentation-first architecture policy in `CLAUDE.md`.
- Decision: Designate `spectrum_systems/` as an **evaluation scaffold pending relocation**. It must not be extended with production pipeline logic. Full removal is gated on relocation to a dedicated implementation repository. The artifact boundary CI will be extended (action A-3) to flag this directory mechanically once the enforcement logic is implemented.
- Rationale: Immediate removal would disrupt evaluation workflows that depend on the package. Explicit evaluation-scaffold status makes the boundary violation visible and time-bounded while preserving short-term utility. The governance posture is strengthened by documenting the status rather than leaving it undocumented.
- Implications: `spectrum_systems/` remains temporarily with evaluation-scaffold status documented in `docs/implementation-boundary.md`. No new production logic may be added. Boundary CI extension (A-3) will enforce this mechanically. Once relocated, this directory will be removed and Decision 5 will be updated to reflect closure.

