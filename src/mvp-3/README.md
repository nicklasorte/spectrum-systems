# MVP-3: Transcript Eval Baseline

First quality gate. Validates ingestion phase (MVP-1, MVP-2) before proceeding to extraction.

## 3 Eval Cases

1. schema_conformance: Both artifacts match schemas
2. assembly_manifest_reproducibility: Manifest hash reproducible
3. minimum_content_coverage: Non-empty speakers, sufficient turns

## Gate-1

From design doc: Schema conformance, assembly reproducibility, minimum speaker coverage.

Block condition: Empty transcript, malformed file, non-reproducible manifest.

## Output

- eval_result × 3 (one per case)
- eval_summary (aggregated)
- evaluation_control_decision (allow/block)
- pqx_execution_record

## Tests

- All 3 cases pass for valid artifacts
- Allow decision emitted
- Execution record created
- Fails on missing artifacts
