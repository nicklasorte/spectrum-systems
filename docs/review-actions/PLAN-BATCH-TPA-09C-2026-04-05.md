# Plan — BATCH-TPA-09C — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-09C

## Objective
Close the remaining trust-boundary spoofability and temporal override-validation gaps by tightening corroboration validation and rejecting future-issued overrides with deterministic fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/tpa_complexity_governance.py | MODIFY | Replace string-prefix corroboration checks with validation-driven corroboration acceptance for repeated hardening escalation. |
| spectrum_systems/modules/runtime/agent_golden_path.py | MODIFY | Enforce `issued_at <= enforcement_now` for override applicability and emit explicit fail-closed reason code on violation. |
| tests/test_tpa_complexity_governance.py | MODIFY | Add/adjust deterministic tests for invalid/non-resolvable vs valid corroboration behavior under repeated hardening escalation. |
| tests/test_hitl_override_enforcement.py | MODIFY | Add deterministic test proving future-issued override is rejected with explicit reason code. |
| tests/test_agent_golden_path.py | MODIFY | Keep AG-04 golden-path override tests aligned with new issuance-time bound enforcement semantics. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_tpa_complexity_governance.py`
2. `pytest tests/test_hitl_override_enforcement.py`
3. `pytest tests/test_agent_golden_path.py`

## Scope exclusions
- Do not redesign TPA control-priority policy.
- Do not weaken or modify any schema contract.
- Do not introduce new runtime artifacts.
- Do not modify unrelated governance/control modules.

## Dependencies
- None.
