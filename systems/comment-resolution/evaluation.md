# Evaluation Plan — Comment Resolution Engine

Evaluation assets live in `eval/comment-resolution`.

- **Objectives**: Validate revision lineage handling, schema conformance, disposition quality, and determinism.
- **Datasets/Fixtures**: `eval/comment-resolution/fixtures` covers single-PDF fallback, malformed spreadsheets, multi-revision ordering, missing/mismatched revisions, and already-addressed-in-later-revision cases.
- **Metrics**: Section anchor accuracy, required field completeness, disposition consistency, provenance completeness, run-to-run stability.
- **Blocking Failures**: Missing required revision PDFs, schema violations, unresolved section anchors, non-deterministic outputs.
- **Traceability**: Outputs must include provenance per `schemas/provenance-schema.json` and reference the run manifest per `docs/reproducibility-standard.md`.
- **Review**: Low-confidence or policy-sensitive items route to human review; evaluation should verify routing logic.
