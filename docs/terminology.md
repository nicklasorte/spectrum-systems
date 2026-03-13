# Terminology Alignment

Use these canonical terms to avoid drift and collisions across documents.

- **System**: An automation capability with a defined interface, evaluation plan, and outputs. Lives under `systems/`.
- **Workflow**: Ordered steps a system executes; specified in `workflows/`.
- **Pipeline**: Implementation detail of a workflow; avoid in design docs unless describing execution order.
- **Artifact**: Any structured output (table, figure, narrative, manifest) with provenance.
- **Manifest**: Run-level record capturing inputs, configurations, versions, and validation results.
- **Schema**: Authoritative contract for inputs, intermediates, or outputs.
- **Prompt**: Structured instruction set tied to specific inputs/outputs and versioned alongside schemas.
- **Evaluation Harness**: Deterministic tests that validate correctness, traceability, and reproducibility (`eval/`).
- **Provenance**: Lineage and accountability metadata for an artifact.
- **Reproducibility**: Ability to rerun a workflow with the same inputs/configuration and achieve the same outputs.
- **Compiler (study compiler)**: A system that ingests structured artifacts, validates them, applies transformation passes, and emits packaged outputs with explicit warnings/errors.
