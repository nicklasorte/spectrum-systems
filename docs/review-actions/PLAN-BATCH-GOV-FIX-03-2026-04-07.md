# Plan — BATCH-GOV-FIX-03 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-FIX-03 — Repair run_prompt_with_governance path handling + test expectations

## Objective
Repair wrapper-driven governance preflight execution for prompt files outside repo root without weakening fail-closed behavior, and align tests to canonical blocking output.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| scripts/check_governance_compliance.py | MODIFY | Handle external prompt file paths safely during governed surface classification |
| scripts/run_prompt_with_governance.py | MODIFY | Preserve wrapper fail-closed behavior and improve path display handling |
| tests/test_run_prompt_with_governance.py | MODIFY | Validate pass/fail behavior for external temp paths and canonical blocking output |
| docs/execution_reports/BATCH-GOV-FIX-03_delivery_report.md | CREATE | Persist delivery report for this repair slice |
| docs/roadmaps/NEXT_SLICE.md | MODIFY | Record next recommended slice |
| docs/roadmaps/SLICE_HISTORY.md | MODIFY | Append concise slice summary |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -m pytest tests/test_run_prompt_with_governance.py`
2. `python -m pytest tests/test_governance_prompt_enforcement.py tests/test_governed_prompt_surface_sync.py`
3. `python -m pytest` (if practical)

## Scope exclusions
- Do not redesign governed prompt surface registry structure.
- Do not alter broader contract preflight policy semantics.
- Do not special-case pytest behavior in production code.

## Dependencies
- `docs/governance/strategy_control_doc.md` remains authoritative.
- `docs/governance/prompt_contract.md` and `docs/governance/prompt_execution_rules.md` remain fail-closed policy sources.
