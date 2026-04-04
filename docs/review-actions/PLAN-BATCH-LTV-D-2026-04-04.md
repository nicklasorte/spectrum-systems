# Plan — BATCH-LTV-D — 2026-04-04

## Prompt type
PLAN

## Roadmap item
LT-03 — Policy Extraction + Compression

## Objective
Introduce contract-governed policy candidate extraction, activation lifecycle gating, and conflict management wiring so recurring validated judgment/correction patterns become deterministic policy artifacts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-LTV-D-2026-04-04.md | CREATE | Record required PLAN artifact before multi-file BUILD/WIRE work. |
| PLANS.md | MODIFY | Register this active plan. |
| contracts/schemas/policy_candidate_record.schema.json | CREATE | Contract-first schema for extracted policy candidates. |
| contracts/examples/policy_candidate_record.json | CREATE | Golden-path example for policy candidate contract. |
| contracts/schemas/policy_activation_record.schema.json | CREATE | Contract for governed policy activation/promotion state. |
| contracts/examples/policy_activation_record.json | CREATE | Golden-path example for policy activation contract. |
| contracts/schemas/policy_conflict_record.schema.json | CREATE | Contract for explicit policy conflict emission and resolution metadata. |
| contracts/examples/policy_conflict_record.json | CREATE | Golden-path example for policy conflict contract. |
| contracts/schemas/build_summary.schema.json | MODIFY | Surface policy extraction/activation/conflict references in operator summary outputs. |
| contracts/examples/build_summary.json | MODIFY | Keep golden-path summary example aligned with schema updates. |
| contracts/schemas/batch_handoff_bundle.schema.json | MODIFY | Carry policy refs into bounded handoff memory artifact. |
| contracts/examples/batch_handoff_bundle.json | MODIFY | Keep handoff golden-path aligned with policy propagation fields. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version bumps for modified contracts. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Implement derive/evaluate/conflict policy logic and integrate into cycle artifacts/control wiring. |
| tests/test_system_cycle_operator.py | MODIFY | Add deterministic extraction, activation, conflict, gating, rollout, and integration coverage. |
| tests/test_contracts.py | MODIFY | Ensure new contract examples validate in contract test surface. |
| tests/test_contract_enforcement.py | MODIFY | Assert manifest registration/versioning for new and updated contracts. |

## Contracts touched
- CREATE `policy_candidate_record` (v1.0.0)
- CREATE `policy_activation_record` (v1.0.0)
- CREATE `policy_conflict_record` (v1.0.0)
- UPDATE `build_summary` (additive version bump)
- UPDATE `batch_handoff_bundle` (additive version bump)
- UPDATE `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign or replace existing autonomy/readiness/eval control layers.
- Do not remove existing fail-closed gates or relax schema validation behavior.
- Do not modify roadmap authority sources outside existing governed integration points.

## Dependencies
- BATCH-LTV-A and BATCH-LTV-B outputs available for lifecycle/precedent/control references.
- Existing failure taxonomy + correction pattern artifacts remain authoritative inputs for extraction.
