# Evaluation Plan — Spectrum Study Compiler

Evaluation assets live under `eval/spectrum-study-compiler` with fixtures in `examples/compiler-input/` and expected outputs in `examples/compiler-output/`.

- **Objectives**: Verify manifest completeness, deterministic pass execution, correct warning/error emission, and packaging integrity.
- **Datasets/Fixtures**: Valid artifacts, missing provenance, duplicate ordering keys, missing required sections, and optional assumption linkage gaps.
- **Metrics**: Schema conformance, manifest completeness, warning/error accuracy, deterministic ordering/formatting, propagation of warnings vs. blocking errors.
- **Blocking Failures**: Emitting outputs without manifests, accepting artifacts with missing provenance, silent drops, ordering ties, missing required sections.
- **Traceability**: Compiler manifest must reference input run manifests and record all passes executed; diagnostics must cite artifact and section IDs.
- **Review**: Warnings must be visible to reviewers; errors must block emission; checksum placeholders allow downstream verification.
