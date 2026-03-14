# Schema Directory Guide

This directory contains authoritative schemas that anchor every system and workflow. Schemas define the contracts that keep automation outputs deterministic and reviewable.

## Inventory

| Schema | Version | Purpose | Required Traceability |
| --- | --- | --- | --- |
| comment-schema.json | 1.1.0 | Authoritative comment/disposition record | Provenance, revision lineage, run manifest reference |
| issue-schema.json | 1.1.0 | Issues/actions extracted from transcripts or comments | Provenance with speaker/time, manifest reference |
| assumption-schema.json | 1.1.0 | Assumptions linked to simulations and artifacts | Provenance, impact level, manifest reference |
| study-output-schema.json | 1.1.0 | Structured study artifacts (tables/figures/narratives) | Provenance, assumptions, manifest reference |
| compiler-manifest.schema.json | 1.0.0 | SYS-004 manifest capturing passes, ordering, and outputs | Provenance reference, revision lineage, checksum placeholders |
| artifact-bundle.schema.json | 1.0.0 | SYS-004 compiled bundle with deterministic ordering | Provenance references, ordering keys, checksum placeholders |
| diagnostics.schema.json | 1.0.0 | SYS-004 diagnostics with explicit warnings/errors | Artifact/section references, provenance, checksum placeholders |
| precedent-schema.json | 1.1.0 | Precedent cases used in decisions | Provenance, review status |
| provenance-schema.json | 1.0.0 | Reusable lineage, validation, and version metadata | Required across all schemas |
| data-lake/comment-resolution-history.json | 1.0.0 | Historical disposition records in the data lake | Provenance, revision info |
| data-lake/assumption-registry.json | 1.0.0 | Persisted assumptions with review metadata | Provenance, impact level |
| data-lake/source-document-registry.json | 1.0.0 | Registered source documents and revisions | Provenance, trust metadata |
| data-lake/study-artifact-metadata.json | 1.0.0 | Metadata for stored study artifacts | Provenance, assumptions, code version |
| data-lake/transcript-output.json | 1.0.0 | Transcript-derived issues persisted in the lake | Provenance, speaker/time |

## Related contracts
- Comment resolution matrix spreadsheet contract (canonical user-facing headers/order for the czar org) lives in `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` with companion doc `docs/comment-resolution-matrix-spreadsheet-contract.md`. Downstream producers (e.g., `working-paper-review-engine`) and consumers (`comment-resolution-engine`) must not alter header names or order.

## Expectations

- Every schema includes `schema_version` and clearly separates required vs optional fields.
- Provenance fields are mandatory for material artifacts; see `provenance-schema.json`.
- Run manifests required by `docs/reproducibility-standard.md` must be referenced where applicable.
- Naming conventions follow `SYS-` for systems, `ASM-` for assumptions, `ISS-` for issues, `ART-` for artifacts, `PRV-` for provenance records.

## Schema Evolution

- Use `MAJOR.MINOR.PATCH` versioning.
- Breaking changes (field removals, renames, or type changes) increment `MAJOR`.
- Additive, backward-compatible fields increment `MINOR`; documentation clarifications or validation-neutral updates increment `PATCH` and do not require downstream repins.
- Deprecated fields remain documented with clear deprecation notes to preserve compatibility.

## Governance

- Follow `docs/schema-governance.md` for approvals and change control.
- When schemas change, update prompts, evaluation assets, and system interfaces in lockstep.
- Record changes in `CHANGELOG.md` and rerun relevant evaluation suites.
