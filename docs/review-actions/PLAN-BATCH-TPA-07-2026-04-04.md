# Plan — BATCH-TPA-07 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-07 — Autonomy Boundaries (TPA-025..TPA-029)

## Objective
Implement fail-closed autonomy boundaries so autonomous actions are scope-gated, maturity-gated, governance-controlled, override-aware, and auditable/replayable.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-07-2026-04-04.md | CREATE | Required plan-first artifact for multi-file contract + runtime update |
| contracts/schemas/autonomy_policy.schema.json | MODIFY | Add explicit autonomy scope/action/signal gating fields |
| contracts/examples/autonomy_policy.json | MODIFY | Golden-path example for updated autonomy policy contract |
| contracts/schemas/autonomy_decision_record.schema.json | MODIFY | Add reason codes and maturity/health evidence used by autonomy boundary decisions |
| contracts/examples/autonomy_decision_record.json | MODIFY | Golden-path example for updated autonomy decision contract |
| contracts/schemas/tpa_policy_candidate.schema.json | MODIFY | Add policy promotion controls + lifecycle states |
| contracts/examples/tpa_policy_candidate.json | MODIFY | Golden-path example for updated policy candidate contract |
| contracts/schemas/override_governance_record.schema.json | MODIFY | Add explicit human override fields and expiry/audit requirements |
| contracts/examples/override_governance_record.json | MODIFY | Golden-path example for updated override contract |
| contracts/schemas/tpa_maturity_signal.schema.json | CREATE | New contract for maturity-gated autonomy execution signal |
| contracts/examples/tpa_maturity_signal.json | CREATE | Golden-path example for maturity signal |
| contracts/schemas/autonomy_audit_record.schema.json | CREATE | New contract for replayable autonomy audit trail entries |
| contracts/examples/autonomy_audit_record.json | CREATE | Golden-path example for autonomy audit trail |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version bumps for changed contracts |
| spectrum_systems/modules/runtime/autonomy_guardrails.py | MODIFY | Implement autonomy scope check, maturity gating, override signal handling, and audit/observability builders |
| spectrum_systems/modules/runtime/tpa_complexity_governance.py | MODIFY | Emit maturity signal and policy promotion controls |
| spectrum_systems/modules/runtime/judgment_engine.py | MODIFY | Populate new override artifact fields |
| tests/test_autonomy_guardrails.py | MODIFY | Add tests for scope gating, maturity gating, fail-closed signals, override behavior, and audit trail |
| tests/test_tpa_complexity_governance.py | MODIFY | Add tests for maturity signal derivation and policy promotion controls |
| tests/test_contracts.py | MODIFY | Validate new contract examples in regression suite |

## Contracts touched
- autonomy_policy (version bump)
- autonomy_decision_record (version bump)
- tpa_policy_candidate (version bump)
- override_governance_record (version bump)
- tpa_maturity_signal (new)
- autonomy_audit_record (new)
- contracts/standards-manifest.json (registry update)

## Tests that must pass after execution
1. `pytest tests/test_autonomy_guardrails.py tests/test_tpa_complexity_governance.py tests/test_contracts.py tests/test_contract_enforcement.py`
2. `pytest tests/test_system_cycle_operator.py tests/test_cycle_runner.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not refactor unrelated runtime orchestration flows.
- Do not change roadmap execution logic outside autonomy-boundary signals.
- Do not alter non-TPA policy schemas.

## Dependencies
- Existing autonomy guardrail and TPA governance contracts/surfaces must remain backward-compatible for deterministic replay.
