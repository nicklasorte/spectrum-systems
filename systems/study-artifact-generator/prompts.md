# Prompts — Study Artifact Generator

Primary prompt: `prompts/report-drafting.md`.

- **Purpose**: Render structured tables/figures and narrative from simulation outputs with explicit provenance and assumptions.
- **Inputs**: Normalized simulation outputs, associated assumptions, target report sections/templates, required figures/tables.
- **Outputs**: Artifacts aligned to `schemas/study-output-schema.json` with provenance and report anchors.
- **Constraints**: Do not infer missing scenarios; cite assumptions; maintain deterministic formatting; avoid speculative claims.
- **Grounding Rules**: Use provided templates; map every narrative statement to a data source; include revision lineage and run manifest ID.
- **Versioning**: Version string in prompt header; changes require evaluation reruns in `eval/study-artifacts`.
