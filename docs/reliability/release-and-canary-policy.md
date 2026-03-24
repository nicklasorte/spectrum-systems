# Release + Canary Policy (SF-14)

SF-14 adds a deterministic release layer on top of existing reliability controls so we can preserve correctness **over time** (not just in one isolated run).

## Why canarying is required

A single eval result can be green while still hiding release risk. Canarying reduces blast radius by evaluating a **candidate** against a known-good **baseline** before full promotion.

SF-14 is intentionally surgical:
- reuses the SF-05 eval execution + control decision path,
- reuses SF-07 coverage/slice visibility,
- emits one governed release decision artifact,
- decides only `promote`, `hold`, or `rollback`.

## Baseline vs candidate model

The CLI (`scripts/run_release_canary.py`) runs both versions through the existing eval harness:

1. Run baseline eval (`run_eval_run`) → `eval_summary`, `eval_results`.
2. Run candidate eval (`run_eval_run`) → `eval_summary`, `eval_results`.
3. Build SF-07 coverage summaries for both (`build_eval_coverage`).
4. Compare deterministic signals:
   - pass-rate delta,
   - coverage-score delta,
   - required-slice regressions,
   - new failures introduced,
   - indeterminate outcomes,
   - control-loop response deltas.

## Promotion vs hold vs rollback

Release decisions are policy-driven by `data/policy/eval_release_policy.json`.

- `promote` (exit code `0`): all thresholds and gates pass.
- `hold` (exit code `1`): one or more thresholds fail, but no rollback trigger fires.
- `rollback` (exit code `2`): deterministic rollback trigger(s) fire; target is `baseline_version`.

Key deterministic rules:
- no silent regression in required slices when `required_slices_must_not_degrade=true`,
- threshold checks are explicit and recorded,
- indeterminate counts as regression when configured,
- control responses (`freeze`, `block`) can gate or trigger rollback,
- rollback reasons are emitted as machine-readable reason codes.

## Policy configuration

`data/policy/eval_release_policy.json` governs:
- minimum canary sample size,
- max pass-rate drop,
- max coverage-score drop,
- whether new failures are allowed,
- whether indeterminate outcomes are treated as regressions,
- control thresholds and blocking responses,
- rollback trigger set.

No release rules are hardcoded in the CLI; they are loaded from this policy file.

## Governed artifact

SF-14 emits `evaluation_release_record`:
- schema: `contracts/schemas/evaluation_release_record.schema.json`
- example: `contracts/examples/evaluation_release_record.json`

The artifact includes:
- baseline/candidate version references,
- prompt/schema/policy/routing version IDs,
- eval/coverage artifact refs,
- canary comparison metrics,
- final decision and reasons,
- deterministic rollback target.

## Local run

```bash
python scripts/run_release_canary.py \
  --baseline-eval-run contracts/examples/eval_run.json \
  --baseline-eval-cases contracts/examples/eval_case.json \
  --candidate-eval-run contracts/examples/eval_run.json \
  --candidate-eval-cases contracts/examples/eval_case.json \
  --baseline-version baseline-2026.03.24.1 \
  --candidate-version candidate-2026.03.24.2 \
  --baseline-prompt-version-id prompt-v1 \
  --candidate-prompt-version-id prompt-v2 \
  --baseline-schema-version contracts-v1 \
  --candidate-schema-version contracts-v2 \
  --baseline-policy-version-id policy-v1 \
  --candidate-policy-version-id policy-v2
```

Output directory default: `outputs/release_canary/`

Key output artifact:
- `outputs/release_canary/evaluation_release_record.json`

## Integration with SF-05 / SF-07 / SF-11

- **SF-05:** reuses canonical eval execution and fail-closed control decision semantics.
- **SF-07:** reuses coverage/slice summaries for required-slice regression detection.
- **SF-11:** reuses control decision response (`allow|warn|freeze|block`) as a governed release signal.

No parallel control or evaluation architecture is introduced.
