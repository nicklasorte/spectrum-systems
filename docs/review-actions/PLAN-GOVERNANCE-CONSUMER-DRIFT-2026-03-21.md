# Plan — GOV-CONSUMER-DRIFT — 2026-03-21

## Prompt type
PLAN

## Roadmap item
Prompt BPB — Strategic Knowledge Validation Gate (governance drift remediation follow-up)

## Objective
Eliminate contract consumer-consistency drift by ensuring canonical intended-consumer inputs and governed manifest examples are aligned, then regenerate enforcement artifacts and add deterministic regression coverage.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNANCE-CONSUMER-DRIFT-2026-03-21.md | CREATE | Required multi-file execution plan before BUILD changes |
| PLANS.md | MODIFY | Register this active plan in the repository plan index |
| tests/test_contract_enforcement.py | MODIFY | Add deterministic regression test for intended consumer vs governance manifest alignment |
| governance/reports/contract-dependency-graph.json | MODIFY | Regenerated enforcement output after canonical/source validation |
| docs/governance-reports/contract-enforcement-report.md | MODIFY | Regenerated human-readable enforcement output |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_contract_enforcement.py`
2. `python scripts/check_artifact_boundary.py`
3. `pytest tests/test_cross_repo_compliance_scanner.py -q`
4. `pytest`

## Scope exclusions
- Do not change schema definitions in `contracts/schemas/`.
- Do not weaken enforcement severity or disable consumer-consistency checks.
- Do not edit generated reports as a primary fix without validating canonical sources first.
- Do not modify downstream repositories outside this repo.

## Dependencies
- docs/vision.md reviewed before implementation.
- Existing governance manifest examples in `governance/examples/manifests/` remain canonical for cross-repo enforcement inputs.
