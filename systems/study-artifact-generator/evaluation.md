# Evaluation Plan — Study Artifact Generator

Evaluation assets live in `eval/study-artifacts`.

- **Objectives**: Verify scenario/metric fidelity, provenance completeness, formatting consistency, and deterministic rendering.
- **Datasets/Fixtures**: Simulation outputs paired with assumptions and expected artifacts/templates.
- **Metrics**: Schema conformance, provenance completeness, template adherence, run-to-run stability.
- **Blocking Failures**: Scenario or metric mismatch, missing assumptions linkage, absent provenance/run manifest, formatting drift across runs.
- **Traceability**: Every artifact must include `derived_from` references to simulations and assumptions plus run manifest metadata (`docs/reproducibility-standard.md`).
- **Review**: Human review expected for narrative tone and visualization choices; evaluation should confirm routing of low-confidence cases.
