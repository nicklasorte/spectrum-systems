# Spectrum Study Compiler (SYS-004)

Compile validated SYS-003 outputs into a deterministic, reviewable bundle with explicit diagnostics and reproducibility manifests.

## Purpose
Turn study artifacts, provenance, and manifests into a packaged deliverable that downstream report assembly can consume without re-validation.

## Bottleneck Addressed
BN-003: removes drift between artifact generation and report packaging by enforcing ordering, linkage, and completeness before publication.

## Inputs
- Validated study artifacts from SYS-003 aligned to `schemas/study-output-schema.json`.
- Provenance records and run manifests aligned to `schemas/provenance-schema.json`.
- Assumption registry references and section anchors required for packaging.
- Rule packs and template constraints (versioned) that define blocking vs. warning conditions.

## Outputs
- Compiler manifest aligned to `schemas/compiler-manifest.schema.json`.
- Artifact bundle aligned to `schemas/artifact-bundle.schema.json`.
- Diagnostics aligned to `schemas/diagnostics.schema.json` with explicit warnings/errors.
- Export/package descriptor (format/ordering) for downstream report assembly.

## Dependencies
- SYS-003 Study Artifact Generator (source of artifacts, assumptions, and provenance).
- Provenance and reproducibility standards (`docs/data-provenance-standard.md`, `docs/reproducibility-standard.md`).
- Schema governance rules in `docs/schema-governance.md`.

## Compiler Passes (deterministic order)
1. **Input validation pass** — validate schemas for artifacts, provenance, manifests; reject missing revision lineage.
2. **Provenance integrity pass** — confirm `derived_from`, run manifest references, and hash placeholders are present and consistent.
3. **Assumption linkage pass** — verify every artifact links to required assumptions/precedents; flag optional gaps as warnings.
4. **Artifact completeness pass** — enforce required sections, artifact IDs, and checksum placeholders; detect duplicates.
5. **Section assembly pass** — order artifacts by section/anchor using declared deterministic rules; record ordering keys in manifest.
6. **Diagnostics and warnings pass** — collate warnings/errors with codes, severity, and references to artifact/section IDs.
7. **Packaging/export pass** — emit bundle plus manifest/diagnostics; block emission on any errors; propagate warnings.

## Failure Conditions (block emission)
- Missing or invalid provenance/run manifest references.
- Duplicate artifact or section IDs after ordering.
- Required sections absent or empty.
- Assumption linkage missing for required sections/artifacts.
- Non-deterministic ordering rules (undefined sort keys or ties).

## Deterministic Ordering Rules
- Sort artifacts first by declared section order, then by `ordering_key` within section; ties must be rejected.
- Record ordering rule, section order, and final artifact order in the compiler manifest.
- Export package must include checksums/placeholders for bundles to allow downstream verification.

## Human Review Checkpoints
- Review all warnings before publication; errors block automatically.
- Confirm dropped artifacts with rationale captured in diagnostics.
- Approve ordering and section coverage when optional artifacts are omitted.
