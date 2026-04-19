# TPA Early Contract Sync + Auto-Repair

TPA now runs an early, fast contract-sync check before heavy contract preflight evaluation.

## Why
Late failures were occurring when schema/example/manifest contract surfaces drifted during artifact renames.

## What TPA checks early
For changed contract-bearing paths, TPA checks alignment between:
- schema `artifact_type` const
- example `artifact_type`
- standards-manifest `artifact_type` entry
- standards-manifest `example_path`
- required-field presence in touched examples when deterministic fill is possible

TPA emits `tpa_contract_sync_check_record`.

## Auto-repair scope (bounded)
When mismatch classes are deterministic and policy-safe, TPA attempts bounded repair and emits:
- `tpa_contract_sync_repair_plan_record`
- `tpa_contract_sync_repair_result_record`

Eligible auto-repair classes:
- schema/example artifact_type rename drift
- manifest example-path drift
- missing manifest entry for touched artifact type
- deterministic example required-field fill (`artifact_type`)

## Fail-closed scope
TPA does **not** auto-repair ambiguous semantic or policy changes.
If mismatches remain after repair, preflight fails closed and escalates.

## One-layer rule
This is an early catch-and-repair layer only.
The existing contract preflight remains authoritative and still runs.
