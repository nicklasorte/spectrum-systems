# Run Evidence Correlation Rule

Every execution across the Spectrum Systems ecosystem must emit a correlated evidence bundle where all artifacts share the same `run_id`. The bundle is only valid when every artifact references an identical `run_id`.

## Required artifacts
- `run_manifest.json`
- `evaluation_results.json`
- `contract_validation_report.json`
- `provenance.json`

Engines and pipelines must propagate the `run_id` through every artifact they generate for a run. The evidence bundle is incomplete and should be rejected if any required file is missing or if `run_id` values diverge.

## Why correlation matters
- Reconstruct system runs end-to-end without guesswork.
- Enable reliable debugging and anomaly isolation.
- Support maturity evaluation with traceable execution proof.
- Underpin architecture reviews with verifiable evidence.
- Enable automated observability analysis and ecosystem-level reasoning.

## Rule
A run is not considered valid unless all evidence artifacts share the same `run_id`.
