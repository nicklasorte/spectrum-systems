# Reproducibility Standard

Reproducibility ensures that a run can be repeated with the same inputs, configuration, and models to produce the same outputs. It complements provenance (what happened) with execution fidelity (can it happen again the same way).

## Principles
- **Deterministic paths**: Given fixed inputs, prompts, rules, and models, outputs should be identical.
- **Complete manifests**: Each run ships a manifest describing inputs, configurations, model hashes, and rule/prompt versions.
- **Stable identifiers**: Every artifact and intermediate has a stable ID tied to its lineage.
- **Environment capture**: Record model versions, parameter settings, and any non-deterministic seeds.
- **Validation-first**: Blocks execution when required inputs, revisions, or schemas are missing.

## Required Metadata
Every run manifest should include:
- run_id, system_id, interface_version
- input manifests (with source paths, checksums, revisions)
- configuration parameters and feature flags
- model names, versions, and temperature/seed settings
- prompt and rule pack versions
- schema versions for inputs and outputs
- timestamps for start/end
- validation outcomes (pass/fail with reasons)
- reviewer identity and review status (if applicable)

## Relationship to Provenance
- Provenance captures lineage and responsibility for artifacts.
- Reproducibility captures how to rerun the activity identically.
- Both are required; provenance without reproducibility hides drift, and reproducibility without provenance hides accountability.

## Enforcement Expectations
- Systems must emit a run manifest as part of their outputs.
- Manifests must be referenced in downstream artifacts via provenance fields.
- Evaluation harnesses should verify that reruns with the same manifest produce the same outputs or flag drift.
- Temperature, randomness, or external dependencies must be fixed or recorded; if not possible, document the nondeterminism explicitly.

## References
- `docs/data-provenance-standard.md` for lineage fields.
- `schemas/provenance-schema.json` for expected provenance payloads.
- System-specific expectations live in `systems/<system>/interface.md`.
