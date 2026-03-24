# Eval Coverage and Slice Summaries (SF-07)

## Purpose

SF-07 adds a deterministic, artifact-first visibility layer over existing eval execution so teams can answer:

1. what eval cases exist,
2. what slices those cases cover,
3. where required coverage is missing,
4. how results break down by slice,
5. whether aggregate pass rate is hiding concentrated failures.

This slice is **reporting/visibility**, not a replacement for SF-05 CI gating.

## Why aggregate pass rate is misleading

A single aggregate pass rate can hide severe concentration risk:

- one critical slice can be failing while low-risk slices pass,
- required slices can have zero cases,
- indeterminate outcomes can mask unresolved quality risk.

SF-07 resolves this by emitting governed per-slice summaries and explicit required-slice gaps.

## Slice model on `eval_case`

`eval_case` now supports additive metadata used for coverage assignment:

- `slice_tags` (preferred canonical slice IDs)
- `domain_tags` (legacy/domain fallback tags)
- `risk_class` (`critical|high|medium|low`)
- `priority` (`p0|p1|p2|p3`)

Coverage computation requires at least one slice tag per case (`slice_tags` or `domain_tags`).

## Required-slice policy

Policy file: `data/policy/eval_coverage_policy.json`

Supported controls:

- `required_slices[]`
- `optional_slices[]`
- `minimum_cases_per_required_slice`
- `minimum_pass_rate_by_risk_class`
- `indeterminate_counts_as_failure`
- `indeterminate_is_blocking` (canonical alias; defaults fail-closed)
- `gap_severity_mapping`

The script reads policy values at runtime (no hardcoded required-slice thresholds).

Indeterminate semantics are fail-closed by default and can only be loosened via explicit governed policy override.
Coverage run IDs are deterministic when not provided explicitly, preventing identity drift in repeated comparisons.

## Generated artifacts

The canonical CLI emits:

- `eval_coverage_summary.json` (contract: `eval_coverage_summary`)
- `eval_slice_summaries.json` (array of `eval_slice_summary` artifacts)
- `eval_coverage_report.md` (human-readable summary)

Default output directory: `outputs/eval_coverage/`.

## Local usage

Run with defaults:

```bash
python scripts/run_eval_coverage_report.py --output-dir outputs/eval_coverage
```

Run with explicit inputs:

```bash
python scripts/run_eval_coverage_report.py \
  --eval-cases contracts/examples/eval_case.json \
  --eval-results contracts/examples/eval_result.json \
  --dataset contracts/examples/eval_dataset.json \
  --policy data/policy/eval_coverage_policy.json \
  --output-dir outputs/eval_coverage
```

Optional blocking mode (for future wiring):

```bash
python scripts/run_eval_coverage_report.py --blocking-on-gaps
```

By default SF-07 is report-only; SF-05 remains the canonical CI gate.
