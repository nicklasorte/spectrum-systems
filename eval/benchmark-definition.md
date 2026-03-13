# Benchmark Definition

Lightweight standard for how evaluation assets should be defined across systems.

## Components
- **Benchmark definition**: scope, target behaviors, blocking failures, metrics, and acceptance thresholds.
- **Datasets/fixtures**: labeled inputs covering normal, edge, and malformed cases.
- **Gold references**: expected outputs aligned to schemas with provenance.
- **Run manifest expectations**: prompt/rule/model versions, seeds, and configuration parameters.

## Dataset Types
- **Synthetic cases**: crafted to exercise specific logic and failure modes.
- **Realistic examples**: representative inputs drawn from actual workflows with sensitive data removed.
- **Regression cases**: previously failed scenarios to prevent recurrence.

## Structure Requirements
- Store cases under `eval/<system>/fixtures` with a README describing coverage.
- Link each benchmark to the system interface and schemas it validates.
- Record blocking vs. warning outcomes explicitly; benchmarks must fail fast on blocking errors.

## Maintenance
- Update benchmarks when schemas, prompts, or rules change.
- Add new regression cases whenever a failure mode is discovered (`docs/system-failure-modes.md`).
- Track coverage and blocking failures in `eval/test-matrix.md`.
