# Plan — REQUIRED-IDS-SANITIZATION — 2026-03-29

## Prompt type
PLAN

## Roadmap item
Contract drift follow-up hardening (meeting_minutes_record + observability identity enforcement)

## Objective
Ensure deterministic sanitization in agent golden-path tests and enforce fail-closed run/trace identity requirements across meeting-minutes and observability test fixtures.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| tests/test_agent_golden_path.py | MODIFY | Verify/normalize persisted_trace sanitization without in-place mutation and remove merge-remnant logic if present |
| tests/test_meeting_minutes_contract.py | MODIFY | Enforce required `trace_id` fixture value through shared helper usage |
| tests/test_observability_metrics.py | MODIFY | Enforce required `run_id` + `trace_id` fixture values through shared helper usage |
| tests/helpers/required_ids.py | CREATE | Central helper to set default required identity fields in test artifacts |
| tests/test_required_ids_enforced.py | CREATE | Guard regression tests that assert fail-closed behavior when IDs are missing |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_agent_golden_path.py tests/test_meeting_minutes_contract.py tests/test_observability_metrics.py tests/test_required_ids_enforced.py`
2. `pytest`

## Scope exclusions
- Do not weaken schema requirements or mark identity fields optional.
- Do not refactor module/runtime implementation code.
- Do not modify contracts or standards version pins.

## Dependencies
- Existing contract schemas for `meeting_minutes_record` and `observability_metrics` remain authoritative and unchanged.
