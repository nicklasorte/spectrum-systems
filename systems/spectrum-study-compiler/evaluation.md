# Evaluation Plan — Spectrum Study Compiler

Evaluation assets will be added under `eval/study-artifacts` with compiler-specific fixtures.

- **Objectives**: Verify manifest completeness, deterministic pass execution, correct warning/error emission, and packaging integrity.
- **Datasets/Fixtures**: Study artifacts with mixed quality (valid, missing provenance, conflicting scenarios) to exercise passes.
- **Metrics**: Schema conformance, manifest completeness, warning/error accuracy, deterministic ordering/formatting.
- **Blocking Failures**: Emitting outputs without manifests, accepting artifacts with missing provenance, silent drops, non-deterministic packaging.
- **Traceability**: Compiler manifest must reference input run manifests and record all passes executed.
- **Review**: Warnings must be visible to reviewers; errors must block emission.
