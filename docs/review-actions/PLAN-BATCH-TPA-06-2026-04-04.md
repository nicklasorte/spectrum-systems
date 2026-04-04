# Plan — BATCH-TPA-06 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-06 — TPA Strategic Integration (TPA-022, TPA-023, TPA-024)

## Objective
Make TPA artifacts deterministically steer roadmap ordering, control hardening posture, and policy candidate generation without auto-applying policy.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-06-2026-04-04.md | CREATE | Required PLAN artifact before multi-file BUILD scope. |
| spectrum_systems/modules/runtime/tpa_complexity_governance.py | MODIFY | Add deterministic TPA strategic scoring, system health mode, and policy-candidate generation utilities. |
| spectrum_systems/modules/runtime/review_roadmap_generator.py | MODIFY | Integrate TPA artifacts into roadmap prioritization and emit `tpa_priority_score`. |
| contracts/schemas/tpa_policy_candidate.schema.json | CREATE | Contract-first schema for governed policy candidate artifact. |
| contracts/examples/tpa_policy_candidate.json | CREATE | Golden-path example for policy candidate contract. |
| contracts/standards-manifest.json | MODIFY | Publish new `tpa_policy_candidate` contract and bump manifest version. |
| tests/test_tpa_complexity_governance.py | MODIFY | Validate control weighting, policy candidate generation, determinism, and replay-ready behavior. |
| tests/test_review_roadmap_generator.py | MODIFY | Validate roadmap integration with TPA priority signals and deterministic ordering. |
| tests/test_contracts.py | MODIFY | Add contract validation coverage for `tpa_policy_candidate`. |

## Contracts touched
- Create `contracts/schemas/tpa_policy_candidate.schema.json`.
- Add `contracts/examples/tpa_policy_candidate.json`.
- Update `contracts/standards-manifest.json` with version bump and new contract entry.

## Tests that must pass after execution
1. `pytest tests/test_review_roadmap_generator.py tests/test_tpa_complexity_governance.py tests/test_contracts.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change TPA fail-closed gate logic in `pqx_sequence_runner.py`.
- Do not modify unrelated roadmap or prompt queue schemas.
- Do not auto-activate or auto-promote policy candidates.

## Dependencies
- Existing TPA complexity artifacts (`complexity_budget`, `complexity_trend`, `tpa_simplification_campaign`) remain authoritative and must be consumed as-is.
