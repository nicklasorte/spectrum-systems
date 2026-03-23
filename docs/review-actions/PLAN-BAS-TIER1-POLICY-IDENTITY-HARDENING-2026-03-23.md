# Plan — BAS Tier-1 Policy Identity Hardening Completion — 2026-03-23

## Prompt type
PLAN

## Roadmap item
BAS — Tier-1 policy-identity hardening rollout completion

## Objective
Migrate remaining control-chain and replay-governance callers/tests to explicit policy-bearing inputs so decision-grade artifacts fail closed without implicit defaults or placeholder policy linkage.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAS-TIER1-POLICY-IDENTITY-HARDENING-2026-03-23.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| tests/test_control_chain_schema_hardening.py | MODIFY | Migrate helpers/callers to explicit policy-bearing artifacts and governance policy inputs; add hardening tests. |
| tests/test_slo_control_chain.py | MODIFY | Remove legacy implicit-policy assumptions and update fixtures/assertions for explicit policy identity behavior. |
| tests/test_slo_gating.py | MODIFY | Align gating fixture paths with explicit policy-bearing decision-grade expectations where applicable. |
| tests/test_replay_decision_engine.py | MODIFY | Ensure replay decision fixtures are policy-pinned where required by hardening contracts. |
| tests/test_replay_governance.py | MODIFY | Require explicit governance_policy in builder calls and add fail-closed tests. |
| tests/test_replay_governance_control_loop.py | MODIFY | Migrate replay-governance control-loop callers to explicit governance_policy inputs to preserve full-suite compatibility. |
| tests/test_policy_identity_hardening.py | CREATE | Add focused hardening coverage for policy identity and placeholder rejection paths. |
| spectrum_systems/modules/runtime/control_chain.py | MODIFY | Remove remaining governed producer placeholder emission / enforce explicit policy identity fail-closed paths. |
| spectrum_systems/modules/runtime/replay_governance.py | MODIFY | Keep fail-closed governance by requiring explicit governance_policy in decision-grade builder paths. |
| spectrum_systems/modules/runtime/replay_decision_engine.py | MODIFY | Eliminate placeholder policy linkage in governed producer outputs and propagate explicit policy identity/fail-closed behavior. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_control_chain_schema_hardening.py tests/test_slo_control_chain.py tests/test_slo_gating.py tests/test_replay_decision_engine.py tests/test_replay_governance.py tests/test_policy_identity_hardening.py`
2. `pytest`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not make `policy_id` or `policy_version` optional in decision-grade artifacts.
- Do not reintroduce implicit `DEFAULT_POLICY`/governance policy fallbacks.
- Do not weaken schema patterns or allow placeholder values like `"(unknown)"`.
- Do not perform unrelated refactors outside declared control-chain/replay hardening paths.

## Dependencies
- Existing BAS policy hardening fixes must remain intact and authoritative.
