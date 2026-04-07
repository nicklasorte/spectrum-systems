# Plan — BATCH-GOV-FIX-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-FIX-01

## Objective
Repair GOV-NEXT-01-03 integration with the existing contract preflight model by adding deterministic required-surface test mapping for the new governance wrapper while preserving fail-closed governance enforcement.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GOV-FIX-01-2026-04-07.md | CREATE | Required multi-file plan artifact |
| tests/test_run_prompt_with_governance.py | CREATE | Add deterministic evaluation test for `scripts/run_prompt_with_governance.py` required surface |
| docs/execution_reports/BATCH-GOV-FIX-01_delivery_report.md | CREATE | Persist required delivery report artifact |
| docs/roadmaps/NEXT_SLICE.md | MODIFY | Record required next-slice summary |
| docs/roadmaps/SLICE_HISTORY.md | MODIFY | Append concise slice history entry |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -m pytest tests/test_governance_prompt_enforcement.py tests/test_run_prompt_with_governance.py`
2. `python scripts/check_governance_compliance.py --file docs/governance/prompt_templates/roadmap_prompt_template.md`
3. `python scripts/check_governance_compliance.py --text "# Invalid prompt\nOnly arbitrary content"`
4. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD`

## Scope exclusions
- Do not weaken `scripts/run_contract_preflight.py` strategy gating logic.
- Do not remove fail-closed behavior from governance prompt checking.
- Do not introduce alternate governance registries.

## Dependencies
- Use existing preflight artifacts under `outputs/contract_preflight/` as primary diagnosis evidence.
