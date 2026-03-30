# Plan — PQX Next-Step Decision Policy Externalization — 2026-03-30

## Prompt type
PLAN

## Roadmap item
PQX Next-Step Decision Policy Externalization

## Objective
Externalize next-step decision criteria into a governed, schema-validated policy while preserving deterministic fail-closed behavior and replay-stable decision identity.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-NEXT-STEP-DECISION-POLICY-2026-03-30.md | CREATE | Record required PLAN before multi-file contract and orchestration work. |
| PLANS.md | MODIFY | Register this plan in Active plans table. |
| contracts/schemas/next_step_decision_policy.schema.json | CREATE | Introduce governed policy contract for next-step decision criteria. |
| data/policy/next_step_decision_policy.json | CREATE | Publish default policy matching existing next-step behavior. |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY | Load/validate policy, drive decisions from policy mappings, and fail closed on policy faults. |
| contracts/schemas/next_step_decision_artifact.schema.json | MODIFY | Add policy provenance fields required in emitted decision artifacts. |
| contracts/examples/next_step_decision_artifact.json | MODIFY | Keep contract example payloads valid with policy provenance fields. |
| contracts/standards-manifest.json | MODIFY | Register new policy contract and bump next_step_decision_artifact schema version metadata. |
| tests/test_next_step_decision_policy.py | CREATE | Add deterministic policy loading/fail-closed and provenance behavior tests. |
| tests/test_next_step_decision.py | MODIFY | Align existing next-step tests to artifact schema/provenance updates. |

## Contracts touched
- `contracts/schemas/next_step_decision_policy.schema.json` (new, version `1.0.0`)
- `contracts/schemas/next_step_decision_artifact.schema.json` (additive update; schema version bump in manifest)
- `contracts/standards-manifest.json` (contract registry updates)

## Tests that must pass after execution
1. `pytest tests/test_next_step_decision.py tests/test_next_step_decision_policy.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign cycle runner state machine architecture.
- Do not alter prompt-generation or model-coupled logic.
- Do not introduce parallel decision engines.

## Dependencies
- `docs/vision.md` reviewed before structural/contract changes (satisfied).
