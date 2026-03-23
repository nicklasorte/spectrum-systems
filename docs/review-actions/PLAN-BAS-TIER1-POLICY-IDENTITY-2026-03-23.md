# Plan — BAS Tier-1 Policy Identity Hardening — 2026-03-23

## Prompt type
PLAN

## Roadmap item
BAS trust-boundary remediation (Tier-1 policy identity and fail-closed linkage)

## Objective
Enforce fail-closed policy resolution and immutable policy identity propagation across enforcement, gating, control-chain, and replay analysis artifacts without changing policy semantics or thresholds.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAS-TIER1-POLICY-IDENTITY-2026-03-23.md | CREATE | Required PLAN artifact before multi-file BUILD changes |
| spectrum_systems/modules/runtime/control_chain.py | MODIFY | Remove default fallback policy resolution; enforce fail-closed policy identity in control-chain artifacts |
| spectrum_systems/modules/runtime/decision_gating.py | MODIFY | Remove implicit gating fallback behavior and enforce policy identity fields |
| spectrum_systems/modules/runtime/replay_governance.py | MODIFY | Remove implicit default governance policy in decision-grade paths |
| spectrum_systems/modules/runtime/replay_decision_engine.py | MODIFY | Enforce deterministic policy parity comparison with required policy identity |
| contracts/schemas/slo_enforcement_decision.schema.json | MODIFY | Require immutable policy identity fields and reject placeholders |
| contracts/schemas/slo_gating_decision.schema.json | MODIFY | Require immutable policy identity fields and reject placeholders |
| contracts/schemas/slo_control_chain_decision.schema.json | MODIFY | Require immutable policy identity fields and reject placeholders |
| contracts/schemas/replay_decision_analysis.schema.json | MODIFY | Require policy identity in decision summaries for deterministic replay parity |
| tests/test_policy_identity_hardening.py | CREATE | Add targeted Tier-1 hardening tests listed in delivery requirements |

## Contracts touched
- `contracts/schemas/slo_enforcement_decision.schema.json`
- `contracts/schemas/slo_gating_decision.schema.json`
- `contracts/schemas/slo_control_chain_decision.schema.json`
- `contracts/schemas/replay_decision_analysis.schema.json`

## Tests that must pass after execution
1. `pytest tests/test_policy_identity_hardening.py`
2. `pytest tests/test_slo_control_chain.py tests/test_slo_gating.py tests/test_replay_decision_engine.py tests/test_replay_governance.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change policy decision semantics or threshold values.
- Do not redesign policy engine architecture.
- Do not modify unrelated modules outside declared files.
- Do not weaken schema strictness.

## Dependencies
- Existing BAS policy registry and enforcement pipeline contracts remain authoritative.
