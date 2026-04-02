# Plan — CON-037-FIX — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-037 FIX — Default PQX Execution Policy CI/Preflight Compatibility Hardening

## Objective
Preserve default PQX-required governed execution while correcting commit-range preflight authority handling so missing execution-context is treated as authority-unknown pending deterministic evidence resolution, not direct-run by default.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-037-FIX-CI-PREFLIGHT-COMPAT-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file fix. |
| PLANS.md | MODIFY | Register the CON-037 fix plan in active plans table. |
| spectrum_systems/modules/runtime/pqx_execution_policy.py | MODIFY | Refine policy state model and commit-range missing-context semantics. |
| scripts/run_contract_preflight.py | MODIFY | Add deterministic authority evidence resolution and policy reporting/wiring. |
| tests/test_contract_preflight.py | MODIFY | Add regression tests for unknown-authority resolution and commit-range behavior. |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest -q tests/test_contract_preflight.py`
2. `pytest -q tests/test_contracts.py`
3. `pytest -q tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `python scripts/run_contract_preflight.py --execution-context pqx_governed --changed-path scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/pqx_execution_policy.py --changed-path tests/test_contract_preflight.py`
6. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/contract_preflight_ci_style`
7. `PLAN_FILES='docs/review-actions/PLAN-CON-037-FIX-CI-PREFLIGHT-COMPAT-2026-04-02.md PLANS.md spectrum_systems/modules/runtime/pqx_execution_policy.py scripts/run_contract_preflight.py tests/test_contract_preflight.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions

- Do not remove default PQX-required governed policy.
- Do not weaken fail-closed behavior for governed authority evidence.
- Do not redesign PQX runner or certification/promotion seams.
- Do not introduce heuristic text inference.

## Dependencies

- CON-037 baseline policy module and preflight wiring already present on current branch.
