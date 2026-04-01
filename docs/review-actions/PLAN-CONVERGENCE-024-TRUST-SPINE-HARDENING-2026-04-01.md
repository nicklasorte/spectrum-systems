# Plan — CONVERGENCE-024 TRUST-SPINE HARDENING — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CONVERGENCE-024 trust-spine hardening single-slice convergence fix

## Objective
Close known trust-boundary gaps across evaluation-control provenance, promotion authority gating, and gate-proof evidence separation while preserving fail-closed deterministic behavior.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CONVERGENCE-024-TRUST-SPINE-HARDENING-2026-04-01.md | CREATE | Required plan artifact before BUILD execution. |
| PLANS.md | MODIFY | Register active CONVERGENCE-024 plan per repository plan norms. |
| contracts/schemas/evaluation_control_decision.schema.json | MODIFY | Require and validate threshold_context provenance in decision artifact schema. |
| contracts/standards-manifest.json | MODIFY | Publish schema version bump for updated evaluation_control_decision contract. |
| contracts/examples/evaluation_control_decision.json | MODIFY | Keep canonical example aligned with required threshold_context and schema version. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Emit threshold_context, deduplicate threshold validation, preserve fail-closed context semantics. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Harden promotion authority checks for required refs, policy/replay semantics, coverage normalization, and blocking vocabulary normalization. |
| scripts/run_control_loop_certification.py | MODIFY | Separate gate proof groups and derive booleans from group-specific references. |
| tests/test_evaluation_control.py | MODIFY | Add threshold_context and comparative/runtime regression coverage. |
| tests/test_sequence_transition_policy.py | MODIFY | Add promotion trust-spine authority and coverage/vocabulary regression tests. |
| tests/test_policy_backtesting.py | MODIFY | Add comparative backtesting regression guard for threshold_context-required artifacts. |
| tests/test_policy_backtest_accuracy.py | MODIFY | Add fail-closed/backtest recommendation regressions tied to threshold context handling. |
| tests/test_policy_enforcement_integrity.py | MODIFY | Add comparative integrity regression guards under threshold_context changes. |
| tests/test_end_to_end_failure_simulation.py | MODIFY | Add end-to-end regression coverage for threshold_context/backtesting continuity. |
| tests/test_control_loop_certification.py | MODIFY | Add gate-proof evidence separation regressions and CLI coverage updates. |
| tests/test_enforcement_engine.py | MODIFY | Contract-preflight-required downstream consumer alignment for evaluation_control_decision schema v1.2.0 required fields. |
| tests/fixtures/autonomous_cycle/eval_coverage_summary_allow.json | CREATE | Deterministic allow-path coverage fixture for promotion authority gate after required coverage ref hardening. |

## Contracts touched
- `contracts/schemas/evaluation_control_decision.schema.json` (additive required field + version bump)
- `contracts/standards-manifest.json` (`evaluation_control_decision` version metadata update)

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_control.py tests/test_sequence_transition_policy.py tests/test_cycle_runner.py tests/test_policy_backtesting.py tests/test_policy_backtest_accuracy.py tests/test_policy_enforcement_integrity.py tests/test_end_to_end_failure_simulation.py tests/test_control_loop_certification.py`
2. `pytest -q tests/test_replay_engine.py tests/test_control_loop_certification.py tests/test_cycle_runner.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight_convergence_024 --changed-path contracts/schemas/evaluation_control_decision.schema.json --changed-path spectrum_systems/modules/runtime/evaluation_control.py --changed-path spectrum_systems/orchestration/sequence_transition_policy.py --changed-path scripts/run_control_loop_certification.py --changed-path tests/test_evaluation_control.py --changed-path tests/test_sequence_transition_policy.py --changed-path tests/test_cycle_runner.py --changed-path tests/test_policy_backtesting.py --changed-path tests/test_policy_backtest_accuracy.py --changed-path tests/test_policy_enforcement_integrity.py --changed-path tests/test_end_to_end_failure_simulation.py --changed-path tests/test_control_loop_certification.py`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign sequence transition state machine.
- Do not redesign control-loop certification orchestration.
- Do not remove comparative_analysis threshold context mode.
- Do not introduce new framework-level validation abstractions.
- Do not modify unrelated schemas/contracts outside declared trust-spine surfaces.

## Dependencies
- Existing RED-021 trust-spine hardening artifacts and fixtures remain baseline inputs for this convergence slice.
