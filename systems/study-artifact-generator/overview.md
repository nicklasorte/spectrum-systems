# Study Artifact Generator (SYS-003)

Purpose: transform simulation outputs into structured study artifacts and report-ready sections with embedded provenance.

- **Bottleneck**: BN-003 — manual translation of simulation outputs into report artifacts slows delivery and loses traceability.
- **Inputs**: Simulation outputs (tables/figures), study templates, assumptions and model parameters, rendering preferences.
- **Outputs**: Structured artifacts aligned to `schemas/study-output-schema.json`, narratives with citations, provenance and manifest references.
- **Upstream Dependencies**: Simulation run metadata, assumption registry, prompt/rule versions.
- **Downstream Consumers**: Report assembly workflows, decision briefs, spectrum study compiler.
- **Related Assets**: `schemas/study-output-schema.json`, `schemas/assumption-schema.json`, `prompts/report-drafting.md`, `eval/study-artifacts`.
- **Lifecycle Status**: Design complete; evaluation cases expanding (`docs/system-status-registry.md`).
