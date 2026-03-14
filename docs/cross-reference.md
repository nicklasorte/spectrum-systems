# Cross-Reference Index: SYS-003 → SYS-004

Purpose: make the handoff between the Study Artifact Generator (SYS-003) and Spectrum Study Compiler (SYS-004) explicit and traceable.

## Handoff Map
- **Upstream (SYS-003) outputs**: artifacts aligned to `schemas/study-output-schema.json`, assumption links (`schemas/assumption-schema.json`), and provenance records (`schemas/provenance-schema.json`).
- **Downstream (SYS-004) inputs**: the above artifacts plus run manifests and packaging rules defined in `workflows/spectrum-study-compiler.md`.
- **Bundling contracts**: `schemas/compiler-manifest.schema.json`, `schemas/artifact-bundle.schema.json`, `schemas/diagnostics.schema.json`.
- **Prompts**: generation (`prompts/report-drafting.md`) feeds validation/packaging (`prompts/spectrum-study-compiler.md`).

## Deterministic Ordering and Traceability
- Ordering rules are declared in `workflows/spectrum-study-compiler.md` and recorded in `manifest.ordering` plus `diagnostics.ordered_artifact_ids`.
- Provenance must remain intact across the handoff; missing provenance is a blocking error per the compiler workflow.
- Hash/checksum placeholders in manifests, bundles, and diagnostics enable downstream reproducibility checks.

## Evaluation References
- SYS-003 validation: `eval/study-artifacts`.
- SYS-004 compilation and packaging: `eval/spectrum-study-compiler` with fixtures under `examples/compiler-input/` and expected outputs under `examples/compiler-output/`.

## Quick Links
- System overviews: `systems/study-artifact-generator/overview.md`, `systems/spectrum-study-compiler/overview.md`
- Workflows: `workflows/study-artifact-generator.md`, `workflows/spectrum-study-compiler.md`
- Interfaces: `systems/study-artifact-generator/interface.md`, `systems/spectrum-study-compiler/interface.md`
