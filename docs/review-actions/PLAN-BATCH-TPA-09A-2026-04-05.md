# Plan — BATCH-TPA-09A — 2026-04-05

## Prompt type
PLAN

## Roadmap item
TPA-ACT-08B-AR-01, TPA-ACT-08B-AR-02

## Objective
Harden trust boundaries by adding expiration-bound HITL override semantics and deterministic corroboration-gated dampening for repeated TPA-local hardening escalation.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-09A-2026-04-05.md | CREATE | Required plan artifact for this multi-file trust-boundary BUILD slice. |
| PLANS.md | MODIFY | Register this plan in the active-plan index. |
| contracts/schemas/hitl_override_decision.schema.json | MODIFY | Add required override expiration semantics and max validity bound fields. |
| contracts/examples/hitl_override_decision.json | MODIFY | Update canonical example to satisfy new expiration semantics. |
| contracts/standards-manifest.json | MODIFY | Publish schema version bump metadata for hitl_override_decision. |
| spectrum_systems/modules/runtime/agent_golden_path.py | MODIFY | Enforce override expiry fail-closed at runtime enforcement boundary. |
| spectrum_systems/modules/runtime/tpa_complexity_governance.py | MODIFY | Add deterministic repeated-escalation dampening rule requiring non-TPA corroboration. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Wire dampening inputs/history from authoritative TPA control path. |
| tests/test_agent_golden_path.py | MODIFY | Add expiry and max-validity enforcement tests for override decisions. |
| tests/test_tpa_complexity_governance.py | MODIFY | Add repeated-escalation dampening + reason-code deterministic tests. |

## Contracts touched
- `hitl_override_decision` (schema version bump)
- `standards_manifest` (publication metadata update)

## Tests that must pass after execution
1. `pytest tests/test_agent_golden_path.py tests/test_tpa_complexity_governance.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-TPA-09A-2026-04-05.md`

## Scope exclusions
- Do not redesign AG runtime flow beyond override expiry trust checks.
- Do not alter non-TPA prioritization systems outside the existing TPA control-priority surface.
- Do not weaken existing fail-closed certification, promotion, or replayability requirements.

## Dependencies
- Existing AG-03/AG-04 HITL review + override enforcement wiring remains authoritative.
- Existing TPA Plan→Build→Simplify→Gate control path remains authoritative.
