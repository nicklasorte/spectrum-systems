# Operational Evidence Standard

## Purpose
Every governed engine execution must emit a minimal, machine-readable evidence bundle. Evidence enables:
- reproducibility and rerun fidelity
- maturity evaluation and readiness scoring
- Claude review substantiation and audit trails
- debugging, anomaly isolation, and reliability analysis
- advisor reasoning and downstream decision support

## Required Evidence Artifacts
Each run must output the following JSON artifacts:
1. `run_manifest.json` — canonical record of the run, inputs, outputs, and execution environment.
2. `evaluation_results.json` — results of automated checks and evaluations performed during the run.
3. `contract_validation_report.json` — contract compliance verdicts and violations for produced artifacts.
4. `provenance.json` — lineage record linking generated artifacts to source artifacts and versioned contracts.
5. `test_evidence_coverage_summary.json` — pre-umbrella decision checkpoint summary proving required tests/evidence are present for any candidate moving to umbrella decisioning.

Artifacts are authoritative and must conform to the schemas in `governance/schemas/`.

## Bundle Layout
Engines and pipelines SHOULD emit evidence alongside produced artifacts using a predictable layout:

```
artifacts/
  <run_id>/
    evidence/
      run_manifest.json
      evaluation_results.json
      contract_validation_report.json
      provenance.json
    outputs/
      ... engine outputs ...
```

Evidence files must be written for every governed run, even when the run fails or is partial. Pipelines should archive the entire evidence directory to support replay and review.

## Artifact Expectations
### run_manifest.json
- Records run identity, engine metadata, status, timing, and environment fingerprint (repo, commit SHA, runtime).
- Lists all inputs and outputs with their artifact type, path, and governing contract name/version.
- Optional notes capture anomalies, feature flags, or partial coverage explanations.
- Schema: `governance/schemas/run_manifest.schema.json`.

### evaluation_results.json
- Captures evaluation checks executed during the run with pass/fail/warn results and optional metrics.
- Aggregates totals for passed, failed, and warning checks to summarize run quality.
- Schema: `governance/schemas/evaluation_results.schema.json`.

### contract_validation_report.json
- Provides the contract validation outcome for each governed artifact, including violations with severities.
- Must be generated even when validation fails; violations enumerate the specific field-level issues.
- Schema: `governance/schemas/contract_validation_report.schema.json`.

### provenance.json
- Links each generated artifact back to its source artifacts, producing engine, and contract version.
- Records timestamped lineage with repository and commit markers to enable deterministic replay.
- Schema: `governance/schemas/provenance.schema.json`.

### test_evidence_coverage_summary.json
- Must be emitted at the pre-umbrella decision checkpoint for governed execution runs that propose umbrella progression.
- Summarizes required tests, artifact evidence references, pass/failure state, and explicit missing-evidence flags.
- Runs lacking this artifact at umbrella checkpoint are invalid and must fail closed.

## Usage Guidance
- Engines MUST emit all five artifacts on every run (success, partial, or failure) when umbrella decision checkpoints are in scope; otherwise the first four remain mandatory baseline evidence.
- Pipelines SHOULD verify evidence against the published schemas before accepting run outputs.
- Claude reviews and maturity assessments SHOULD cite evidence bundle paths for claims.
- Advisory engines SHOULD consume evidence to reason about reliability and readiness at higher maturity levels.

## Run Evidence Correlation
- `run_id` MUST appear in `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, `provenance.json`, and `test_evidence_coverage_summary.json` when that checkpoint artifact is required.
- Engines and pipelines MUST propagate the same `run_id` into every evidence artifact produced during execution.
- Evidence bundles with missing artifacts or mismatched `run_id` values are invalid and must be rejected or regenerated.

## Examples
A complete example evidence bundle lives in `governance/examples/evidence-bundle/`. Use it as a template when instrumenting engines and pipelines.
