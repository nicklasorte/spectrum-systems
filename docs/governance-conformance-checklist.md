# Governance Conformance Checklist

Use this checklist to help implementation repositories verify compliance with the spectrum-systems governance layer before release or deployment.

## Repository Identity
- [ ] `system_id` declared in repository metadata and documentation.
- [ ] Implementation repository linked to its governing system record.

## Contract Compliance
- [ ] Consumed contracts pinned to versions declared in `contracts/standards-manifest.json`.
- [ ] No contract definitions reimplemented locally.

## Schema Compliance
- [ ] Canonical schemas imported from spectrum-systems.
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
