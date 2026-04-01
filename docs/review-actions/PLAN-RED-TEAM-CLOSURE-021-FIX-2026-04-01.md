# Plan — RED-TEAM-CLOSURE-021-FIX — 2026-04-01

## Prompt type
PLAN

## Roadmap item
RED-TEAM-CLOSURE-021-FIX — Threshold context boundary repair (runtime vs comparative analysis)

## Objective
Repair RED-021 regression by introducing explicit threshold-resolution context boundaries so active runtime stays hardened while comparative policy analysis/backtesting/simulation can evaluate looser/tighter candidates deterministically.

## Root cause
RED-021 applied runtime-hardening threshold-relaxation constraints globally in `build_evaluation_control_decision`, causing comparative-analysis paths (policy backtesting, policy enforcement integrity checks, end-to-end failure simulation) to fail when intentionally testing looser policy thresholds.

## Impacted seams
- Runtime threshold resolver in `evaluation_control.py`
- Comparative policy consumers calling `build_evaluation_control_decision(..., thresholds=...)`
  - `runtime/policy_backtesting.py`
  - `governance/policy_enforcement_integrity.py`
  - `governance/end_to_end_failure_simulation.py`
- Regression test surfaces validating policy comparison and simulation behavior

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RED-TEAM-CLOSURE-021-FIX-2026-04-01.md | CREATE | Required plan-first artifact for RED-021 fix bundle. |
| PLANS.md | MODIFY | Register fix plan per repo convention. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Add explicit threshold-context boundary for runtime vs comparative analysis. |
| spectrum_systems/modules/runtime/policy_backtesting.py | MODIFY | Route threshold use through comparative-analysis context. |
| spectrum_systems/modules/governance/policy_enforcement_integrity.py | MODIFY | Route comparative threshold checks through comparative-analysis context. |
| spectrum_systems/modules/governance/end_to_end_failure_simulation.py | MODIFY | Route comparative scenario thresholds through comparative-analysis context. |
| tests/test_policy_backtesting.py | MODIFY | Validate comparative mode accepts looser/tighter candidate thresholds. |
| tests/test_policy_backtest_accuracy.py | MODIFY | Validate comparative accuracy path no longer fails at threshold parsing. |
| tests/test_policy_enforcement_integrity.py | MODIFY | Validate policy integrity comparative checks remain governed/non-crashing. |
| tests/test_end_to_end_failure_simulation.py | MODIFY | Validate end-to-end simulation comparative threshold path remains functional. |
| tests/test_evaluation_control.py | MODIFY | Validate runtime vs comparative threshold-context boundary behavior and fail-closed semantics. |

## Contracts touched
None expected.

## Tests that must pass after execution
1. `pytest -q tests/test_policy_backtesting.py tests/test_policy_backtest_accuracy.py tests/test_policy_enforcement_integrity.py tests/test_end_to_end_failure_simulation.py tests/test_replay_engine.py tests/test_sequence_transition_policy.py tests/test_cycle_runner.py tests/test_evaluation_control.py`
2. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight --changed-path spectrum_systems/modules/runtime/evaluation_control.py --changed-path spectrum_systems/modules/runtime/policy_backtesting.py --changed-path spectrum_systems/modules/governance/policy_enforcement_integrity.py --changed-path spectrum_systems/modules/governance/end_to_end_failure_simulation.py --changed-path spectrum_systems/modules/runtime/replay_engine.py --changed-path spectrum_systems/orchestration/sequence_transition_policy.py`
3. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-RED-TEAM-CLOSURE-021-FIX-2026-04-01.md spectrum_systems/modules/runtime/evaluation_control.py spectrum_systems/modules/runtime/policy_backtesting.py spectrum_systems/modules/governance/policy_enforcement_integrity.py spectrum_systems/modules/governance/end_to_end_failure_simulation.py spectrum_systems/modules/runtime/replay_engine.py spectrum_systems/orchestration/sequence_transition_policy.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not weaken RED-021 replay/promotion hardening.
- Do not redesign orchestration or schema architecture.
- Do not introduce implicit fallback from runtime to comparative thresholds.

## Dependencies
- RED-021 hardening commit remains in place.
- ALIGNMENT_020 trust-spine constraints remain authoritative for runtime paths.
