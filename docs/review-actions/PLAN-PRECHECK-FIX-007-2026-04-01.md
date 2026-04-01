# Plan — PRECHECK-FIX-007 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
PRECHECK-FIX-007 — Contract Preflight Changed-Path Detection Repair

## Objective
Repair contract preflight changed-path detection so CI and local runs do not fail on missing `HEAD~1`, while preserving strict fail-closed enforcement through broader governed scanning fallbacks.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PRECHECK-FIX-007-2026-04-01.md | CREATE | Required plan artifact for multi-file BUILD repair. |
| scripts/run_contract_preflight.py | MODIFY | Implement robust changed-path detection order, fallback metadata, and degraded full-governed scan behavior. |
| tests/test_contract_preflight.py | MODIFY | Add tests for explicit paths, base/head diff, missing HEAD~1, shallow fallback, full scan fallback, and report metadata. |
| .github/workflows/artifact-boundary.yml | MODIFY | Pass event-aware refs/SHAs and tighten checkout depth for preflight reliability in CI. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
2. `pytest tests/test_contract_preflight.py -q`
3. `python scripts/run_contract_preflight.py --changed-path contracts/schemas/roadmap_eligibility_artifact.schema.json --output-dir outputs/contract_preflight_smoke`

## Scope exclusions
- Do not remove or weaken the contract preflight gate.
- Do not modify governed contract schemas for this fix.
- Do not change unrelated workflows.

## Dependencies
- Existing `analyze_contract_impact` behavior remains the deterministic seam impact source.
