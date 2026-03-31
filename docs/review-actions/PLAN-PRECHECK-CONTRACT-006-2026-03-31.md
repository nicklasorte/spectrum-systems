# Plan — PRECHECK-CONTRACT-006 — 2026-03-31

## Prompt type
PLAN

## Roadmap item
PRECHECK-CONTRACT-006 — Contract Change Preflight Gate

## Objective
Add a fail-closed preflight contract gate that detects changed governed schemas, maps likely impact, runs targeted compatibility checks, and blocks broad pytest when seam propagation is incomplete.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PRECHECK-CONTRACT-006-2026-03-31.md | CREATE | Required multi-file execution plan for this BUILD slice. |
| scripts/run_contract_preflight.py | CREATE | Implement preflight detection, impact mapping, targeted validations, masking detection, and report emission. |
| tests/test_contract_preflight.py | CREATE | Deterministic tests for changed-contract detection, impacted seam mapping, targeted smoke selection, and masking classification. |
| .github/workflows/artifact-boundary.yml | MODIFY | Wire preflight to run before broad pytest and block pytest when preflight fails. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_contract_preflight.py --help`
2. `pytest tests/test_contract_preflight.py -q`
3. `pytest tests/test_contract_impact_analysis.py tests/test_roadmap_eligibility.py tests/test_next_step_decision.py tests/test_next_step_decision_policy.py tests/test_cycle_runner.py -q`

## Scope exclusions
- Do not modify contract schema contents or standards manifest versions.
- Do not refactor orchestration runtime modules outside preflight integration.
- Do not change unrelated CI workflows.

## Dependencies
- Existing contract impact analyzer in `spectrum_systems/governance/contract_impact.py` remains the deterministic base for seam detection.
