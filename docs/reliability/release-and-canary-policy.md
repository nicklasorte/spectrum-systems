# Release + Canary Policy (SF-14)

SF-14 is the canonical release/canary governance boundary for candidate-vs-baseline promotion decisions.

## Canonical interface

- Contract: `contracts/schemas/evaluation_release_record.schema.json`
- Example: `contracts/examples/evaluation_release_record.json`
- Policy: `data/policy/eval_release_policy.json`
- CLI: `scripts/run_release_canary.py`

## Decision meanings

- `promote`: candidate is eligible for progression.
- `hold`: candidate is blocked pending review/remediation.
- `rollback`: candidate must be rejected and baseline is the rollback target.

## Explicit precedence

Decision precedence is deterministic and explicit:

1. `rollback` (highest)
2. `hold`
3. `promote` (lowest)

The implementation never allows later checks to downgrade `rollback`/`hold` into `promote`.

## Fail-closed behavior

SF-14 fails closed. The release path is non-promote when any of the following occur:

- policy load failure,
- comparison execution error,
- coverage mismatch when parity is required,
- required slice degradation,
- new failure identities,
- indeterminate outcomes when policy blocks them,
- artifact write failure.

## Coverage and slice semantics

Release canary compares baseline and candidate for:

- aggregate pass-rate delta,
- coverage score delta,
- required slice regressions,
- coverage parity mismatches,
- new fail-case identities,
- indeterminate case identities.

`required_slices_no_regression` and `coverage_parity_required` are policy-governed hard gates.

## Exit-code contract

`scripts/run_release_canary.py` exit codes are strict and canonical:

- `0` = `promote`
- `1` = `hold`
- `2` = `rollback`

Operational exceptions and artifact emission failures never return `0`.

## Artifact emission guarantee

`evaluation_release_record.json` is emitted for all non-crash paths:

- promote
- hold
- rollback
- handled operational error

If artifact emission itself fails, the process fails closed (`exit 2`).

## Local run

```bash
python scripts/run_release_canary.py \
  --baseline-version baseline-v1 \
  --candidate-version candidate-v2 \
  --baseline-prompt-version-id prompt-v1 \
  --candidate-prompt-version-id prompt-v2 \
  --baseline-schema-version contracts-v1 \
  --candidate-schema-version contracts-v2 \
  --baseline-policy-version-id policy-v1 \
  --candidate-policy-version-id policy-v2
```

Default output directory: `outputs/release_canary/`.

## CI integration

`.github/workflows/release-canary.yml` runs the canonical CLI directly and uploads release artifacts for audit/debug. Non-zero exits are not masked.
