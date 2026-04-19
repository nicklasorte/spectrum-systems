# SLI/SLO Governance Layer

Service Level Indicators and Objectives for pipeline reliability.

## SLI Targets

- eval_pass_rate: ≥99%
- drift_rate: ≤0.5% per day
- reproducibility_score: ≥95%
- cost_per_run: ≤$5
- trace_coverage: ≥95%

## SLO Definitions

Each SLI has an SLO with:
- Target value
- Error budget (e.g., 1% = 99% target)
- Grace period (variance allowance)
- Window (e.g., 7 days)

## Burn-Rate Detection

Tracks trends in measurements:
- WARN: burn_rate > 2x sustainable
- FREEZE: burn_rate > 5x sustainable
- BLOCK: burn_rate > 10x sustainable

Uses hysteresis: 3 consecutive high-burn samples before alerting.
