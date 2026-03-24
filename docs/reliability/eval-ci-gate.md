# Eval CI Gate

## Purpose

`python scripts/run_eval_ci_gate.py` is the canonical fail-closed CI gate for governed evaluation in `spectrum-systems`.
It executes the existing eval flow (`eval_run` + `eval_case`), validates emitted artifacts against canonical contracts,
applies threshold and control-decision blocking rules, and emits a machine-readable result artifact for CI consumption.

## Required inputs and emitted artifacts

### Required inputs
- `--eval-run` (default: `contracts/examples/eval_run.json`)
- `--eval-cases` (default: `contracts/examples/eval_case.json`)
- `--policy` (default: `data/policy/eval_ci_gate_policy.json`)

### Emitted artifacts
By default under `outputs/eval_ci_gate/`:
- `eval_summary.json`
- `evaluation_control_decision.json`
- `evaluation_ci_gate_result.json` (machine-readable CI summary)

## Blocking conditions (fail-closed)

The gate blocks and exits non-zero when any of the following occurs:

1. Required eval artifacts are missing.
2. Any required or emitted eval artifact fails schema validation.
3. Any eval outcome is indeterminate.
4. Configured thresholds are not met.
5. Control decision resolves to a blocking response (`freeze` or `block` by policy).
6. Execution errors prevent trustworthy evaluation.

## Exit code behavior

- `0`: gate **pass**
- `1`: gate **fail** (threshold failure)
- `2`: gate **blocked** (missing/invalid/indeterminate/control-block/execution error)

## CI wiring

The lifecycle workflow calls this gate and uploads its artifact bundle:

- Workflow: `.github/workflows/lifecycle-enforcement.yml`
- Step: `python scripts/run_eval_ci_gate.py --eval-run ... --eval-cases ... --output-dir outputs/eval_ci_gate`
- Artifact upload path: `outputs/eval_ci_gate/`

Workflow failure is driven directly by the gate exit code.

## Local usage

Run with defaults:

```bash
python scripts/run_eval_ci_gate.py --output-dir outputs/eval_ci_gate
```

Run with explicit fixtures/policy:

```bash
python scripts/run_eval_ci_gate.py \
  --eval-run path/to/eval_run.json \
  --eval-cases path/to/eval_cases.json \
  --policy data/policy/eval_ci_gate_policy.json \
  --output-dir outputs/eval_ci_gate
```
