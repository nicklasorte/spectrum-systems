# Provenance Identity Continuity Contract

## Purpose
Define deterministic fail-closed continuity rules for `run_id` and `trace_id` in runtime artifact flows.

## Trace continuity
`trace_id` **must remain constant** for child artifacts created within the same execution lineage unless an explicit policy allows trace override.

Required constant-trace seams:
- replay artifact -> evaluation/control consumption
- evaluation/control artifact -> certification/governance consumption
- persisted trace reload validation

## Run continuity
`run_id` is the same-run provenance anchor.

`run_id` **must match** across linked artifacts when same-run continuity is required (default).

`run_id` **may differ** only when an explicit cross-run policy is set at the seam entrypoint, e.g.:
- `identity_policy.allow_cross_run_reference = true` in done certification input refs.

## Allowed cross-run / cross-trace references
A reference is allowed only if all conditions hold:
1. the seam policy explicitly enables the exception (no implicit allowance), and
2. required identity fields are present and non-empty strings, and
3. all other non-overridden identity anchors remain consistent.

If these conditions are not met, the seam fails closed with deterministic provenance mismatch errors.
