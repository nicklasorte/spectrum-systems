# Spectrum Study Compiler Evaluation (SYS-004)

## Purpose
Validate that SYS-004 compiles SYS-003 outputs deterministically, enforces provenance and assumption linkage, and emits explicit diagnostics before packaging.

## Test Cases
- Successful compile — inputs in `examples/compiler-input/valid-bundle-input.yaml` should produce outputs like `examples/compiler-output/valid-bundle.json`.
- Missing required provenance — block compilation and emit errors as in `examples/compiler-output/missing-provenance-failure.json`.
- Duplicate artifact IDs or ordering collisions — fail with deterministic ordering errors as in `examples/compiler-output/duplicate-section-failure.json`.
- Missing required sections — fail when required anchors are absent; populate errors referencing missing section IDs.
- Optional artifact absent — warn but allow packaging, following the pattern in `examples/compiler-output/missing-assumption-linkage-warning.json`.
- Deterministic ordering check — repeated runs must produce identical `artifact_order` and `ordered_artifact_ids` values.

## Expected Outcomes
- Warnings propagate; errors block bundle/export emission.
- Manifests, bundles, and diagnostics must validate against `schemas/compiler-manifest.schema.json`, `schemas/artifact-bundle.schema.json`, and `schemas/diagnostics.schema.json`.
- Ordering rules and revision lineage must be recorded in manifests and diagnostics.
