# Spectrum Study Compiler (SYS-004)

Purpose: compile study inputs, artifacts, and manifests into a validated, packaged deliverable with explicit warnings/errors.

- **Bottleneck**: BN-003 — inconsistent handoffs between artifact generation, validation, and report packaging introduce drift and missing traceability.
- **Inputs**: Normalized study artifacts, provenance records, run manifests, assumption registries, decision/context metadata.
- **Outputs**: Validated compiled package (tables/figures/narratives), manifest of passes applied, warnings/errors, and publication-ready bundle.
- **Upstream Dependencies**: Study Artifact Generator outputs, provenance schema, reproducibility manifests, rule packs for validation.
- **Downstream Consumers**: Report assembly, decision briefs, archival stores.
- **Related Assets**: `schemas/study-output-schema.json`, `schemas/provenance-schema.json`, `prompts/report-drafting.md` (compiler-aware), `eval/study-artifacts` (compiler cases to be added).
- **Lifecycle Status**: Interfaces and design in draft; evaluation cases pending (`docs/system-status-registry.md`).

## Study runner scaffold
- Deterministic study runner prototype lives in `spectrum_systems/study_runner/`.
- CLI: `python run_study.py study_config.yaml` loads YAML configs, executes the pipeline, and emits outputs to `outputs/` (`tables/`, `figures/`, `maps/`, `results.json`, `study_summary.json`).
