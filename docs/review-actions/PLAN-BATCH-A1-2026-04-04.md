# Plan — BATCH-A1 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-A1 — Autonomy Guardrails

## Objective
Add a schema-bound governed autonomy guardrail layer that deterministically decides continue/stop/require_human_review/escalate from explicit runtime signals and blocks unattended continuation unless policy conditions allow it.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-A1-2026-04-04.md | CREATE | Required PLAN-first artifact for BATCH-A1 multi-file implementation. |
| PLANS.md | MODIFY | Register BATCH-A1 active plan entry. |
| contracts/schemas/autonomy_policy.schema.json | CREATE | Canonical policy contract for governed autonomy continuation/stop/review/escalation thresholds. |
| contracts/examples/autonomy_policy.json | CREATE | Golden-path policy example for deterministic contract validation. |
| contracts/schemas/autonomy_decision_record.schema.json | CREATE | Canonical decision artifact contract for replayable autonomy guardrail outcomes. |
| contracts/examples/autonomy_decision_record.json | CREATE | Golden-path autonomy decision record example. |
| contracts/schemas/build_summary.schema.json | MODIFY | Surface autonomy decision/reason visibility in operator summary output. |
| contracts/schemas/batch_handoff_bundle.schema.json | MODIFY | Carry unresolved autonomy blockers across bounded handoff state. |
| contracts/schemas/next_cycle_input_bundle.schema.json | MODIFY | Carry autonomy blocker references into next governed cycle input bundle. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version updates for touched artifacts. |
| spectrum_systems/modules/runtime/autonomy_guardrails.py | CREATE | Deterministic autonomy guardrail evaluation engine with fail-closed enforcement. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Integrate autonomy guardrail evaluation, decision artifacts, and blocker propagation into cycle outputs. |
| spectrum_systems/modules/runtime/next_governed_cycle_runner.py | MODIFY | Refuse unattended execution unless autonomy decision allows continue. |
| tests/test_autonomy_guardrails.py | CREATE | Unit coverage for deterministic/fail-closed autonomy guardrail engine behavior. |
| tests/test_system_cycle_operator.py | MODIFY | Validate autonomy artifact emission and operator/handoff propagation. |
| tests/test_next_governed_cycle_runner.py | MODIFY | Validate next-cycle refusal when autonomy decision is not continue and malformed/missing policy fail-closed behavior. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Validate deterministic autonomy blocker propagation in handoff bundle derivation. |

## Contracts touched
- `autonomy_policy` (new)
- `autonomy_decision_record` (new)
- `build_summary` (additive)
- `batch_handoff_bundle` (additive)
- `next_cycle_input_bundle` (additive)
- `standards_manifest` (updated registrations)

## Tests that must pass after execution
1. `pytest tests/test_autonomy_guardrails.py`
2. `pytest tests/test_system_cycle_operator.py`
3. `pytest tests/test_roadmap_multi_batch_executor.py`
4. `pytest tests/test_next_governed_cycle_runner.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`
8. `pytest`
9. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing control decision taxonomy outside governed autonomy gating output.
- Do not add agent reasoning or model-driven decision logic.
- Do not add unmanaged runtime state or hidden memory.
- Do not refactor unrelated runtime modules or test suites.

## Dependencies
- Existing bounded control decisions and integration-validation outputs remain authoritative input signals.
- Existing `run_system_cycle` and `run_next_governed_cycle` remain the governed execution seam for continuation gating.
