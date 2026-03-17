# Evaluation Layer

> **Canonical evaluation directory.** This is the authoritative location for all per-system evaluation harnesses. See `evals/` for the shared evaluation dataset guidance and rubrics (deprecated as a standalone directory — its content is superseded by the governance in this directory and `contracts/schemas/evaluation_manifest.schema.json`).

Evaluation assets live per system under `eval/<system>/` with fixtures and README files. Use `eval/test-matrix.md` to see coverage and blocking expectations.

- `comment-resolution/` — SYS-001 fixtures for revision validation, section mapping, and disposition determinism.
- `transcript-to-issue/` — SYS-002 fixtures for extraction precision/recall and provenance completeness.
- `study-artifacts/` — SYS-003/SYS-004 fixtures for scenario/metric fidelity, provenance, and deterministic rendering/packaging.
- `benchmark-definition.md` — standard for defining datasets, gold references, and blocking failures.
- `test-matrix.md` — matrix of systems, datasets, metrics, and blocking failures.
