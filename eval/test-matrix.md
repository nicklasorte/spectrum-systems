# Evaluation Test Matrix

Maps systems to their evaluation assets and target behaviors. Add rows as systems mature.

| System | Evaluation Scope | Datasets / Fixtures | Primary Checks | Blocking Failures |
| --- | --- | --- | --- | --- |
| SYS-001 Comment Resolution Engine | Comment parsing, section mapping, disposition drafting | `eval/comment-resolution/fixtures` | Schema conformance, revision validation, section anchor accuracy, determinism | Missing required revisions, schema violations, non-deterministic dispositions |
| SYS-002 Transcript-to-Issue Engine | Issue extraction and classification from transcripts | `eval/transcript-to-issue` | Precision/recall on labeled transcripts, provenance completeness, owner/priority correctness | Missing speaker/timestamp, misclassified priorities, unstable outputs |
| SYS-003 Study Artifact Generator | Rendering tables/figures and narratives from simulations | `eval/study-artifacts` | Scenario/metric fidelity, provenance linkage, formatting consistency, deterministic rendering | Scenario mismatch, missing assumptions linkage, formatting drift |
| SYS-004 Spectrum Study Compiler | Compiler passes across artifacts and manifests | `eval/spectrum-study-compiler` with `examples/compiler-input` and `examples/compiler-output` | Manifest completeness, deterministic ordering, packaging accuracy, propagation of warnings | Missing manifest fields, emitted artifacts without validation, dropped warnings/errors, ordering ties |
