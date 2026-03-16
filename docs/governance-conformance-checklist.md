# Governance Conformance Checklist

Use this checklist to help implementation repositories verify compliance with the spectrum-systems governance layer before release or deployment.

## Repository Identity
- [ ] `system_id` declared in repository metadata and documentation.
- [ ] Implementation repository linked to its governing system record.

## Governance Declaration
- [ ] Machine-readable governance declaration file (`.governance-declaration.json`) present in the repository and pinned to current versions from `contracts/standards-manifest.json`. Use `contracts/governance-declaration.template.json` as the starting point.

## Contract Compliance
- [ ] Consumed contracts pinned to versions declared in `contracts/standards-manifest.json`.
- [ ] No contract definitions reimplemented locally.

## Schema Compliance
- [ ] Canonical schemas imported from spectrum-systems (`contracts/schemas/` for contract schemas; root `schemas/` for supplemental structural schemas).
- [ ] Schema versions pinned.
- [ ] No field renaming or reordering.

## Provenance
- [ ] Artifacts include required provenance metadata.
- [ ] Source artifacts preserved when required by contracts.

## Rules
- [ ] Rule packs imported from spectrum-systems when applicable.
- [ ] Local overrides documented.

## Evaluation
- [ ] Evaluation harness sourced from `eval/`.
- [ ] Evaluation harness executed and pass/fail results recorded per `eval/test-matrix.md`.

## Architecture Decisions
- [ ] All architecture decisions are covered by ADRs in `docs/adr/` or explicitly deferred with a documented trigger condition.

## CI Enforcement
- [ ] `artifact-boundary` CI workflow is green (no prohibited data artifacts or implementation code).
- [ ] `review-artifact-validation` CI workflow is green (all design-review artifacts conform to schema).

## System Lifecycle
- [ ] Current lifecycle gate status confirmed and recorded in `docs/system-status-registry.md`.

## Related governance documents
- `ADR-006-governance-manifest-policy-engine.md` — governance manifest model and policy engine
- `ADR-007-phase-1-governance-enforcement.md` — Phase 1 enforcement strategy
- `ADR-008-schema-authority-designation.md` — canonical schema authority designation
- `docs/governance-enforcement-roadmap.md` — four-phase enforcement roadmap
- `docs/implementation-boundary.md` — production-code boundary rules
- `contracts/governance-declaration.template.json` — canonical governance declaration template
