# Plan — BAE Decision Dialect Unification — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAE — Control Loop Integration trust-hardening follow-up

## Objective
Remove Tier-1 ambiguity in evaluation budget decisions by enforcing a single canonical control-loop dialect and centralizing status→response mapping.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAE-DIALECT-UNIFICATION-2026-03-22.md | CREATE | Required PLAN artifact before multi-file BUILD changes |
| PLANS.md | MODIFY | Register active plan |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Define and host single canonical status→response mapping and adapter helper |
| spectrum_systems/modules/runtime/evaluation_budget_governor.py | MODIFY | Remove duplicate mapping logic and route all control-loop/system mapping through canonical helper |
| scripts/run_evaluation_control_loop.py | MODIFY | Use one canonical control-loop adapter function |
| contracts/schemas/evaluation_budget_decision.schema.json | MODIFY | Remove dialect ambiguity via explicit discriminator and strict branch validation |
| tests/test_evaluation_budget_governor.py | MODIFY | Replace legacy mapping assertions with canonical unification guarantees |
| tests/test_evaluation_control_loop.py | MODIFY | Add control-loop regression checks for legacy rejection and adapter parity |

## Contracts touched
- `contracts/schemas/evaluation_budget_decision.schema.json` (dialect discriminator, strict enum boundaries)

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_budget_governor.py tests/test_evaluation_control_loop.py`
2. `pytest -q tests/test_contracts.py`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change BAF enforcement behavior.
- Do not change threshold semantics beyond dialect unification and mapping delegation.
- Do not add new decision semantics.
- Do not refactor unrelated runtime modules.

## Dependencies
- Existing BAE monitor and validator artifacts remain the source of control-loop inputs.
