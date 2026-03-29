# Plan — CONTRACT-DRIFT-MMR-OBSERVABILITY — 2026-03-29

## Prompt type
PLAN

## Roadmap item
Contract drift follow-up (meeting minutes + observability fixtures/builders)

## Objective
Apply a minimal surgical fix so shared meeting-minutes and observability builders emit required trace/run metadata under current schemas, without weakening validation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CONTRACT-DRIFT-MMR-OBSERVABILITY-2026-03-29.md | CREATE | Required plan for multi-file follow-up migration |
| PLANS.md | MODIFY | Register active plan |
| tests/test_meeting_minutes_contract.py | MODIFY | Add required trace_id in shared base meeting-minutes fixture |
| spectrum_systems/modules/observability/metrics.py | MODIFY | Ensure ObservabilityRecord serialization path emits run_id and trace_id |

## Contracts touched
None (builder/fixture alignment only).

## Tests that must pass after execution
1. `pytest tests/test_meeting_minutes_contract.py -q`
2. `pytest tests/test_observability_metrics.py -q`
3. `pytest -q`

## Scope exclusions
- Do not relax schemas.
- Do not mass-edit individual tests when shared builders can be fixed.
- Do not change unrelated modules.

## Dependencies
- Existing canonical schemas for `meeting_minutes_record` and `observability_record` are authoritative.
