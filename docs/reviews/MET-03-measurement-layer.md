# MET-03 — Measurement, Bottleneck, and Leverage Engine Review

## Prompt type
BUILD

## Why MET-03 was needed
MET-01-02 produced an artifact-backed seed loop and partial proof chain, but the
dashboard could only show that the system was partial. It could not yet compute
where the system is constrained, what is fragile, or what to fix next. MET-03
adds a measurement layer that produces those answers as governed artifacts.

## What was added
Three new artifacts live under `artifacts/dashboard_metrics/`:

- `bottleneck_record.json` — dominant bottleneck system, constrained loop leg,
  warning/block counts per system, supporting evidence with sources, priority
  rule, and explicit `bottleneck_confidence` (`artifact_backed` or
  `derived_estimate`).
- `leverage_queue_record.json` — prioritized fix queue with documented formula,
  weights, and per-item `failure_prevented`, `signal_improved`, and
  `source_artifacts_used`.
- `risk_summary_record.json` — fallback/unknown/missing eval/missing trace
  counts, override count (`unknown` until a history artifact exists), proof
  chain coverage, and a sourced top-risks list.

`artifacts/dashboard_seed/failure_mode_dashboard_record.json` is extended with
`severity`, `frequency`, `systems_affected`, and `trend`. Frequency and trend
remain `unknown` until historical artifacts exist — no fake precision.

`/api/intelligence` is wired to expose `bottleneck`, `bottleneck_confidence`,
`leverage_queue`, and `risk_summary`, and the dashboard UI consumes them.

## How bottlenecks are computed
1. The seeded loop (`AEX → PQX → EVL → TPA → CDE → SEL` with `REP/LIN/OBS/SLO`
   overlays) is read from `minimal_loop_snapshot.json`.
2. Per-system warning and block counts are read directly from the artifact-
   backed status fields on each seeded record.
3. Governance legs (`EVL`, `CDE`, `TPA`) are prioritized when ranking the
   dominant bottleneck because they gate promotion. Promotion-gating signals
   (e.g. `CDE.payload.promotion_gate = blocked`) increase the rank further.
4. `bottleneck_confidence` is `artifact_backed` only when the dominant leg is
   read directly from artifact-backed status fields and supporting evidence
   names the source artifact paths. Otherwise the record degrades to
   `derived_estimate` and the API surfaces that.

## How leverage is computed
The formula is documented in the artifact and applied identically by the API:

```
leverage_score = (severity_weight * systems_impacted) / effort_weight
boosts (multiplicative):
  blocks_promotion or affects governance legs (EVL/CDE/TPA) -> 1.4
  repeat_failure                                            -> 1.15
  reduces fallback or unknown coverage                      -> 1.15
weights:
  severity: high=3, medium=2, low=1
  effort:   high=3, medium=2, low=1, unknown=2
```

Three contract rules are enforced both at artifact creation and at API render
time:
- no recommendation without source (`source_artifacts_used` non-empty)
- no recommendation without `failure_prevented`
- no recommendation without `signal_improved`

Items missing any of those fields are filtered before the leverage queue is
returned to the dashboard.

## What is artifact-backed vs derived
| Surface                                    | Provenance        |
|--------------------------------------------|-------------------|
| `bottleneck_record.json`                   | artifact_store    |
| `leverage_queue_record.json`               | artifact_store    |
| `risk_summary_record.json`                 | artifact_store    |
| Per-item `source_artifacts_used` paths     | artifact_store    |
| `frequency` and `trend` on failure modes   | unknown (no history yet) |
| `override_count` in risk summary           | unknown (no override log yet) |
| Dashboard fallback queue (when API empty)  | derived           |
| Bottleneck fallback (when MET artifact missing) | derived_estimate |

## Limitations
- Single-case seed. Bottleneck counts and leverage rankings reflect one seeded
  case (`dashboard-seed-001`); rankings will harden once additional cases land.
- No historical artifacts. Frequency and trend remain `unknown` by design.
- Override count is `unknown`. There is no override audit log artifact yet.
- Effort estimates are sourced from artifact context, not historical actuals.
- Many non-loop systems still resolve to `stub_fallback` and continue to
  degrade trust posture (this is intentional — no fake green).

## What MET-03 does NOT do
- It does not promote anything. `branch_update_allowed` still requires
  `terminal_state == "ready_for_merge"` via PR review.
- It does not mark any signal `PASS` unless it is fully proven; partial loop
  legs continue to render `warn`/`partial`.
- It does not compute trend lines. Trends remain `unknown`.

## Next gaps
1. Seed additional cases so frequency, trend, and ranking can graduate from
   `unknown` to artifact-backed.
2. Introduce an override audit log artifact so `override_count` becomes a real
   number rather than `unknown`.
3. Replace remaining `stub_fallback` system rows with artifact-backed snapshots
   (already the highest-leverage non-governance fix).
4. Add full SEL certification artifact to clear the `observe_only` enforcement
   boundary.
5. Expand REP replay dimensions (`distribution_shift`, `long_horizon`) so the
   EVL coverage gap can be closed end-to-end.

## Explicit posture statement
- **This is not full production telemetry.**
- **The dominant bottleneck is `EVL` (artifact-backed, partial coverage).**
- **The dashboard now identifies where the system is constrained, what is
  fragile, and what to fix next — every recommendation is sourced.**
- **Fallback and unknown signals continue to block green; nothing is `PASS`
  unless fully proven.**
