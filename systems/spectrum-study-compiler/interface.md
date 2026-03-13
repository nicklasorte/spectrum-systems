# Spectrum Study Compiler — Interface (SYS-004)

## Purpose
Compile normalized study artifacts into a validated, packaged deliverable with explicit pass/fail signaling and reproducibility manifests.

## Inputs
- Structured artifacts from the Study Artifact Generator aligned to `schemas/study-output-schema.json`.
- Provenance records for each artifact plus the associated run manifest (`docs/reproducibility-standard.md`).
- Assumption registry references and decision/context metadata.
- Validation/packaging rules (versioned) that define required checks and error classes.

## Schemas Used
- `schemas/study-output-schema.json`
- `schemas/provenance-schema.json`
- Manifests that enumerate compiler passes, rule versions, and outputs.

## Outputs
- Compiled package of validated artifacts with consistent formatting and report anchors.
- Compiler manifest: inputs, passes executed, warnings/errors emitted, schema versions, and model/prompt versions (when used).
- Summary of blocking errors and warnings suitable for reviewers.

## Validation Rules
- All inputs must pass schema validation before compilation; missing provenance is blocking.
- Compiler passes must be deterministic and ordered; pass list recorded in manifest.
- Warnings vs. errors must be explicit; errors block emission, warnings propagate in the manifest.
- Any dropped artifact must be recorded with reason.

## Evaluation Method
- Initial evaluation uses `eval/study-artifacts` cases to confirm manifest completeness, warning/error propagation, and deterministic packaging.
- Blocking failures: missing manifest fields, silent acceptance of invalid artifacts, non-deterministic ordering or formatting.

## Versioning
- Interface and pass set versions are captured in compiler manifests.
- Changes to pass ordering or validation rules require re-running evaluation cases and updating `docs/system-status-registry.md`.
