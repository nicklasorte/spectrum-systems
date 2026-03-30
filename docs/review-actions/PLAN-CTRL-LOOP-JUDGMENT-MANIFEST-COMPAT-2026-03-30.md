# Plan — CTRL-LOOP-01-JUDGMENT-MANIFEST-COMPAT — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 surgical hardening — cycle_manifest judgment field propagation

## Objective
Restore repository-wide cycle_manifest compatibility by explicitly adding required judgment fields to all cycle_manifest producers/fixtures/templates with neutral deterministic defaults where judgment is not required.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-JUDGMENT-MANIFEST-COMPAT-2026-03-30.md | CREATE | Required plan for multi-file hardening slice |
| PLANS.md | MODIFY | Register active hardening plan |
| tests/test_cycle_observability.py | MODIFY | Update base manifest helper to canonical required judgment fields |
| tests/fixtures/autonomous_cycle/cycle_status_blocked_manifest.json | MODIFY | Keep fixture schema-valid under strict cycle_manifest |
| runs/cycle-0001/cycle_manifest.json | MODIFY | Align repo-native manifest template with canonical schema |

## Contracts touched
- None (no schema change)

## Tests that must pass after execution
1. `pytest tests/test_cycle_observability.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`

## Scope exclusions
- Do not alter cycle_manifest schema required set.
- Do not add observability-only hidden defaulting.
- Do not modify judgment engine or gating semantics.

## Dependencies
- Prior judgment layer slice committed on branch.
