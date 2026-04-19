# TPA Early Contract Sync + Repair-Candidate Handoff

TPA runs an early, fast contract-sync check before heavy contract preflight evaluation.

## Why
Late failures were occurring when schema/example/manifest contract surfaces drifted during artifact renames.

## What TPA does
For changed contract-bearing paths, TPA performs detection and classification for:
- schema `artifact_type` const
- example `artifact_type`
- standards-manifest `artifact_type` entry
- standards-manifest `example_path`
- manifest-declared canonical schema path existence (`contracts/schemas/<artifact_type>.schema.json`)
- canonical schema JSON parse validity
- canonical schema `artifact_type.const` alignment to manifest-declared artifact type
- required-field presence in touched examples when deterministic fill is possible

TPA emits `tpa_contract_sync_check_record`.

## Candidate-generation scope
For deterministic, policy-safe mismatch classes, TPA generates bounded repair candidates and handoff artifacts:
- `tpa_contract_sync_repair_plan_record`
- `tpa_contract_sync_repair_handoff_record`

Eligible candidate classes:
- schema/example artifact_type rename drift
- manifest example-path drift
- missing manifest entry for touched artifact type
- deterministic example required-field fill (`artifact_type`)

## Boundary
TPA does **not** own authoritative contract enforcement or authoritative contract mutation.
TPA only diagnoses, marks eligibility, and prepares deterministic repair candidates for handoff to authorized repair/enforcement paths.

## Fail-closed behavior
Ambiguous or non-derivable mismatches remain fail-closed and continue through authoritative downstream preflight gating.
