# Plan — BATCH-PA — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-PA — Narrow Fix: Program Layer Contract Preflight Block Closure

## Objective
Resolve the exact contract-preflight BLOCK introduced by BATCH-P by restoring downstream roadmap_eligibility artifact compatibility without weakening program-layer governance.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PA-2026-04-03.md | CREATE | Required plan-first artifact for narrow multi-file remediation. |
| PLANS.md | MODIFY | Register active BATCH-PA plan in canonical plan index. |
| tests/test_cycle_runner.py | MODIFY | Update local roadmap_eligibility fixture payload to new required fields/version. |
| tests/test_next_step_decision.py | MODIFY | Update helper eligibility payload to satisfy v1.2.0 contract requirements. |
| tests/test_next_step_decision_policy.py | MODIFY | Update policy tests' eligibility payload to satisfy v1.2.0 contract requirements. |

## Contracts touched
None (no schema shape changes in this fix).

## Tests that must pass after execution
1. `pytest tests/test_program_layer.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_contract_enforcement.py`
4. `pytest tests/test_cycle_runner.py`
5. `pytest tests/test_next_step_decision.py`
6. `pytest tests/test_next_step_decision_policy.py`
7. `python scripts/run_contract_enforcement.py`
8. `python scripts/run_contract_preflight.py --base-ref <BASE> --head-ref <HEAD> --output-dir outputs/contract_preflight`
9. `PLAN_FILES='...' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change program-layer runtime logic.
- Do not alter contract schemas, standards-manifest versions, or gating policy.
- Do not introduce bypasses or weaken strategy/control enforcement.

## Dependencies
- Existing BATCH-P contracts and orchestration/runtime changes remain as-is; this patch only restores downstream fixture compatibility.
