# Plan — CON-027 Threshold & Policy Semantics Unification — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CON-027 — Threshold & Policy Semantics Unification

## Objective
Make threshold override semantics canonical and explicit so evaluation control, policy backtesting, and governance integrity flows all enforce the same governed threshold interpretation without weakening fail-closed behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-027-THRESHOLD-POLICY-SEMANTICS-UNIFICATION-2026-04-01.md | CREATE | Required plan-first artifact for this multi-file hardening slice |
| PLANS.md | MODIFY | Register active CON-027 plan |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Make canonical threshold semantics explicit and shared across contexts |
| spectrum_systems/modules/runtime/policy_backtesting.py | MODIFY | Route policy threshold parsing through canonical evaluation-control threshold semantics |
| spectrum_systems/modules/governance/policy_backtest_accuracy.py | MODIFY | Update governance validation fixtures/cases to governed-valid thresholds and explicit invalid-policy fail-closed cases |
| spectrum_systems/modules/governance/policy_enforcement_integrity.py | MODIFY | Remove semantically invalid permissive threshold assumptions; align comparative cases to governed semantics |
| spectrum_systems/modules/governance/end_to_end_failure_simulation.py | MODIFY | Ensure VAL-08 backtest path uses governed-valid candidate/baseline threshold sets |
| tests/test_evaluation_control.py | MODIFY | Align comparative-threshold tests with canonical governed semantics |
| tests/test_policy_backtesting.py | MODIFY | Update tests to governed-valid thresholds and explicit invalid relaxed override failures |
| tests/test_policy_backtest_accuracy.py | MODIFY | Align expected outcomes with canonical threshold semantics and explicit fail-closed invalid cases |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_control.py tests/test_policy_backtesting.py tests/test_policy_backtest_accuracy.py tests/test_policy_enforcement_integrity.py tests/test_end_to_end_failure_simulation.py tests/test_sequence_transition_policy.py tests/test_done_certification.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight --changed-path spectrum_systems/modules/runtime/evaluation_control.py --changed-path spectrum_systems/modules/runtime/policy_backtesting.py --changed-path spectrum_systems/modules/governance/policy_enforcement_integrity.py --changed-path spectrum_systems/modules/governance/end_to_end_failure_simulation.py --changed-path tests/test_policy_backtesting.py --changed-path tests/test_policy_backtest_accuracy.py --changed-path tests/test_policy_enforcement_integrity.py --changed-path tests/test_end_to_end_failure_simulation.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign control-loop architecture or policy model shape.
- Do not weaken fail-closed behavior in runtime or governance seams.
- Do not introduce parallel threshold interpretation logic in downstream modules.
- Do not modify contracts/schemas in this slice.

## Dependencies
- Existing evaluation-control governed-threshold hardening direction must remain authoritative.
- Existing VAL-05/VAL-08/VAL-10 validation artifacts remain in place and are adjusted only for threshold semantic alignment.
