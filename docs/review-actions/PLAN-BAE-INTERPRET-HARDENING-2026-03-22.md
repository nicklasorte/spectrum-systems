# Plan — BAE Interpret Hardening Patch — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAE — Control Loop Integration interpret-layer hardening follow-up

## Objective
Apply a tightly scoped interpret-layer fail-closed and provenance hardening patch for control-loop monitor record/summary handling, with deterministic regression coverage.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAE-INTERPRET-HARDENING-2026-03-22.md | CREATE | Required written plan before multi-file BUILD changes |
| PLANS.md | MODIFY | Register the new active plan |
| spectrum_systems/modules/runtime/evaluation_monitor.py | MODIFY | Harden healthy-branch semantics and deterministic multi-source provenance in control-loop summary |
| contracts/schemas/evaluation_monitor_summary.schema.json | MODIFY | Add minimal control-loop provenance fields and enforce shape |
| contracts/examples/evaluation_monitor_summary.json | MODIFY | Keep contract example aligned with updated summary schema |
| contracts/standards-manifest.json | MODIFY | Version-bump evaluation_monitor_summary contract metadata per contract authority rules |
| tests/test_evaluation_control_loop.py | MODIFY | Add focused regressions for contradictory/partial payloads and deterministic provenance behavior |

## Contracts touched
- `contracts/schemas/evaluation_monitor_summary.schema.json` (additive provenance fields for control-loop summary)
- `contracts/standards-manifest.json` (`evaluation_monitor_summary` schema_version + last_updated_in bump)

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_control_loop.py tests/test_evaluation_monitor.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not redesign control-loop status thresholds beyond healthy-branch fail-closed guard requirements.
- Do not modify observe/enforce behavior outside evaluation_monitor interpret/summary paths.
- Do not redesign legacy monitor summary schema shapes.
- Do not change evaluation_budget_governor decision mapping.
- Do not perform unrelated refactors or formatting-only changes.

## Dependencies
- Existing BAE control-loop decision, monitor-record, and summary schemas remain authoritative inputs.
