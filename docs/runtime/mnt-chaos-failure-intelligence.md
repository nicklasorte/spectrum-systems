# MNT-CHAOS-01 — Chaos testing and failure intelligence

## Prompt type
BUILD

## Purpose
This slice validates that existing fail-closed runtime checks are active under controlled fault injection and that each failure is emitted as a structured artifact.

The slice is additive:
- no system registry changes
- no owner remapping
- no architecture expansion

## Chaos testing harness
`tests/test_chaos_fail_closed.py` injects deterministic failure scenarios and verifies the runtime never silently succeeds.

Covered scenarios:
1. missing `complexity_justification_record`
2. missing `core_loop_alignment_record`
3. missing `debuggability_record`
4. missing `trace_id` or lineage
5. missing required evals
6. invalid context (empty or conflicting)
7. replay mismatch

Expected outcome for each scenario: a halted or paused runtime outcome only (never silent pass-through).

## Adapter vocabulary normalization
This module is an observational adapter, not an authority surface.

It normalizes authority-shaped source results into neutral fields:
- `observed_outcome` (`passed` | `halted` | `paused`)
- `halt_reasons`
- `reason_code`

## Failure artifact: `failure_record`
The runtime emits `failure_record` whenever normalized observation is `halted` or `paused`.

Schema fields:
- `artifact_type`
- `artifact_id`
- `trace_id`
- `run_id`
- `stage`
- `failure_type` (`BLOCK` | `FREEZE`)
- `reason_code`
- `missing_artifacts`
- `failed_evals`
- `timestamp`

Design guarantees:
- deterministic artifact id from canonicalized payload seed
- no dependency on log scraping
- explicit fail-closed failure typing

## Failure aggregation: `failure_hotspot_report`
`aggregate_failure_hotspots()` computes simple count-based intelligence from recent `failure_record` artifacts.

Fields:
- `time_window`
- `top_reason_codes`
- `failure_counts_by_type`
- `missing_artifact_counts`
- `eval_failure_counts`

Aggregation is intentionally light-weight and deterministic (no external infra).

## Maintain loop (thin)
`run_failure_intelligence_loop()` runs post-cycle and emits:
- `failure_hotspot_report`
- `missing_eval_report`
- `debug_gap_report`

The loop is additive observability over current execution, not a separate runtime system.

## Continuous improvement path
Failure artifacts become stable input for:
- detecting repeated reason codes
- prioritizing missing eval coverage
- closing recurring debug and lineage gaps

This keeps improvement data-driven while preserving existing hard fail-closed semantics.
