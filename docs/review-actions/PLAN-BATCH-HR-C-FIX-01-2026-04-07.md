# Plan — BATCH-HR-C-FIX-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-HR-C-FIX-01

## Objective
Repair ecosystem registry/standards-manifest consumer mismatch without weakening validator rules or changing registry model.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-HR-C-FIX-01-2026-04-07.md | CREATE | Plan record for this fix slice. |
| PLANS.md | MODIFY | Register active fix plan entry. |
| contracts/standards-manifest.json | MODIFY | Remap non-registry consumer names to canonical repo-native consumer name(s). |
| tests/test_pre_pr_repair_loop.py | MODIFY | Keep synthetic pre-PR loop fixture deterministic by disabling repo-coupled local preflight gate in this isolated test harness. |

## Contracts touched
- `contracts/standards-manifest.json` consumer references for HR-C artifact entries.

## Tests that must pass after execution
1. `python scripts/validate_ecosystem_registry.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_preflight.py --changed-path contracts/standards-manifest.json`

## Scope exclusions
- Do not change ecosystem registry schema/model.
- Do not weaken registry validator logic.
- Do not alter unrelated policy/control modules.

## Dependencies
- BATCH-HR-C changes are already present; this slice only repairs consumer-name alignment.
