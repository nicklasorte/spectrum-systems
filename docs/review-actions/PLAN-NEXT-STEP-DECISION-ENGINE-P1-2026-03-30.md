# Plan — NEXT-STEP-DECISION-ENGINE-P1 — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 follow-on controlled next-step decision engine hardening

## Objective
Implement a deterministic, fail-closed next-step decision engine contract + orchestration integration that blocks invalid progression and writes a schema-valid decision artifact.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-NEXT-STEP-DECISION-ENGINE-P1-2026-03-30.md | CREATE | Required PLAN artifact before multi-file BUILD changes. |
| PLANS.md | MODIFY | Register active plan entry. |
| contracts/schemas/next_step_decision_artifact.schema.json | CREATE | Canonical contract for deterministic control-layer next-step decisions. |
| contracts/examples/next_step_decision_artifact.json | CREATE | Golden-path + blocked + drift examples for contract consumers/tests. |
| contracts/standards-manifest.json | MODIFY | Publish and pin next_step_decision_artifact schema version in standards registry. |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add optional next_step_decision_artifact_path field for decision artifact persistence. |
| contracts/examples/cycle_manifest.json | MODIFY | Keep canonical cycle manifest example aligned with updated schema optional field. |
| spectrum_systems/orchestration/next_step_decision.py | CREATE | Deterministic fail-closed decision engine implementation. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Invoke decision engine before progression and persist decision artifact path. |
| spectrum_systems/orchestration/__init__.py | MODIFY | Export next-step decision builder for orchestration package consumers. |
| tests/test_next_step_decision.py | CREATE | Deterministic unit tests for governance/determinism/fail-closed behavior. |
| tests/test_cycle_runner.py | MODIFY | Align existing cycle runner assertion with pre-progression next-step blocking gate semantics. |
| scripts/run_next_step_decision.py | CREATE | Optional CLI for deterministic decision generation and blocking exit behavior. |

## Contracts touched
- `next_step_decision_artifact` (new contract; schema_version `1.0.0`)
- `standards_manifest` (version increment to publish the new contract pin)

## Tests that must pass after execution
1. `pytest tests/test_next_step_decision.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not redesign cycle state model.
- Do not add any planner/agent/LLM behavior.
- Do not refactor unrelated orchestration modules.
- Do not modify non-declared contracts.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- Existing cycle manifest + roadmap/review/execution artifact contracts remain authoritative inputs.
- Existing `cycle_runner` fail-closed behavior remains baseline and must be preserved.
