# Plan — CTRL-LOOP-05 Policy Lifecycle Governance — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-05

## Objective
Add deterministic, artifact-first judgment policy lifecycle governance (lifecycle + rollout artifacts, canary cohort gating, promotion/rollback/revoke rules, registry integration, and integration tests) without introducing a parallel policy plane.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-05-POLICY-LIFECYCLE-2026-03-30.md | CREATE | Required PLAN artifact before grouped multi-file BUILD work |
| PLANS.md | MODIFY | Register active PLAN entry |
| contracts/schemas/judgment_policy.schema.json | MODIFY | Extend status vocabulary to include revoke semantics |
| contracts/schemas/judgment_policy_lifecycle_record.schema.json | CREATE | New governed lifecycle transition artifact contract |
| contracts/schemas/judgment_policy_rollout_record.schema.json | CREATE | New governed rollout/cohort artifact contract |
| contracts/examples/judgment_policy_lifecycle_record.json | CREATE | Golden-path lifecycle artifact example |
| contracts/examples/judgment_policy_rollout_record.json | CREATE | Golden-path rollout artifact example |
| contracts/standards-manifest.json | MODIFY | Publish new contracts and bump standards version |
| spectrum_systems/modules/runtime/judgment_policy_lifecycle.py | CREATE | Deterministic lifecycle/rollout/promotion/rollback/revoke engine |
| spectrum_systems/modules/runtime/judgment_engine.py | MODIFY | Extend policy selection seam with lifecycle-aware deterministic selection |
| tests/test_contracts.py | MODIFY | Ensure new lifecycle artifact examples validate |
| tests/test_judgment_policy_lifecycle.py | CREATE | Integration tests for lifecycle governance and fail-closed behavior |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document lifecycle states, canary cohorting, promotion, rollback/revoke semantics |
| docs/roadmap/system_roadmap.md | MODIFY | Add roadmap compatibility row for policy lifecycle governance slice |

## Contracts touched
- `judgment_policy` (status enum extension)
- `judgment_policy_lifecycle_record` (new)
- `judgment_policy_rollout_record` (new)
- `standards_manifest` publication update

## Tests that must pass after execution
1. `pytest tests/test_contracts.py tests/test_judgment_policy_lifecycle.py`
2. `pytest tests/test_judgment_learning.py tests/test_judgment_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign cycle runner state machine.
- Do not refactor unrelated policy registry modules outside judgment lifecycle seam.
- Do not introduce network/runtime-randomized cohort assignment.

## Dependencies
- CTRL-LOOP-01 through CTRL-LOOP-04 judgment/eval/enforcement/readiness slices must remain intact and are treated as existing prerequisites.
