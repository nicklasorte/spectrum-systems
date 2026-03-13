# Study Artifact Generator — Interface (SYS-003)

## Purpose
Render simulation outputs into structured artifacts and report-ready sections with deterministic formatting and provenance.

## Inputs
- Simulation outputs (tables, figures, logs) with run metadata.
- Assumptions and model parameters associated with the outputs.
- Study templates and target report section anchors.
- Prompt and rule versions referenced in `prompts/report-drafting.md`.

## Schemas Used
- `schemas/study-output-schema.json`
- `schemas/assumption-schema.json`
- `schemas/provenance-schema.json`

## Outputs
- Structured artifacts (tables/figures/narratives) aligned to `study-output-schema.json`.
- Narrative sections with explicit citations and section anchors.
- Run manifest covering inputs, model settings, prompt/rule versions, and schema versions.

## Validation Rules
- Scenario, metric, and unit labels must match source simulations.
- Provenance fields (`derived_from`, `source_document`, `assumptions`) are mandatory.
- Formatting must follow templates; deviations must be flagged.
- Non-determinism (layout or values) across identical manifests is a blocking error.

## Evaluation Method
- Use `eval/study-artifacts` to check scenario/metric fidelity, provenance completeness, formatting consistency, and determinism.
- Blocking failures: missing provenance, scenario/metric mismatch, unreferenced assumptions, formatting drift against templates.

## Versioning
- Interface version recorded in run manifests; prompt/rule updates require re-running evaluations and updating `docs/system-status-registry.md`.
