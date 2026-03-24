# Control-Loop Chaos Tests (SF-12)

## Purpose

SF-12 adds deterministic chaos-style verification for the evaluation control loop so controller behavior is provably correct under malformed, conflicting, incomplete, adversarial, and boundary-condition inputs.

This slice is intentionally surgical:
- Reuses the canonical control decision path (`run_control_loop` → `build_evaluation_control_decision`).
- Adds explicit deterministic synthetic scenarios.
- Emits a machine-readable summary artifact.
- Does not redesign control architecture.

## What “chaos” means here

Chaos in SF-12 is **deterministic scenario stress**, not random fuzzing.
Each scenario is explicit and reproducible with:
- `scenario_id`
- description
- input artifact payload
- expected status/response/decision
- expected reasons

Fixture location:
- `tests/fixtures/control_loop_chaos_scenarios.json`

## Scenario categories covered

The canonical fixture includes deterministic cases for:
- Missing or invalid inputs (null artifact, unsupported type, malformed summary, invalid enums)
- Indeterminate/uncertain outcomes (folded through canonical `failure_eval_case` auto-deny path)
- Threshold boundaries (exact boundary, just above/below)
- Conflicting signals (good pass rate + high drift, trust breach override, severe-combination escalation)
- Blocking states (failure_eval_case auto-deny, trust block, freeze state)
- Determinism (same input run twice in one scenario evaluation)

## Precedence validation

SF-12 validates the controller’s **actual** precedence from current implementation:
- `block` takes precedence over `freeze` when `trust_breach` exists or multiple severe signals are present.
- `freeze` takes precedence over `warn` when `stability_breach` exists.
- `warn` takes precedence over `allow` when non-severe but failing signals exist.
- Healthy inputs yield `allow`.

In shorthand from observed policy behavior:
- `block > freeze > warn > allow`

## Summary artifact

Runner output artifact:
- `artifact_type`: `evaluation_control_chaos_summary`
- `schema_version`: `1.0.0`
- `chaos_run_id`
- `timestamp`
- `scenario_count`
- `pass_count`
- `fail_count`
- `mismatches[]`
- `scenario_results[]`

Default output path:
- `outputs/control_loop_chaos/evaluation_control_chaos_summary.json`

## How to run locally

```bash
python scripts/run_control_loop_chaos_tests.py \
  --scenarios tests/fixtures/control_loop_chaos_scenarios.json \
  --output outputs/control_loop_chaos/evaluation_control_chaos_summary.json
```

Exit codes:
- `0`: all scenarios matched expectations
- `1`: one or more scenario mismatches
- `2`: runner/config error

## Relationship to SF-05 and SF-07

- **SF-05 (CI gate)** remains the primary promotion gate.
- **SF-07 (coverage + slice summaries)** reports breadth and slice-risk visibility.
- **SF-12 (this slice)** closes controller trust gaps by proving deterministic fail-closed and precedence behavior under controlled stress scenarios.
