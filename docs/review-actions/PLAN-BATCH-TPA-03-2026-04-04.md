# Plan — BATCH-TPA-03 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-03 (TPA-013, TPA-015, TPA-016)

## Objective
Make TPA enforcement mandatory at promotion and done-certification boundaries for explicitly governed scope, with deterministic fail-closed policy evaluation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-03-2026-04-04.md | CREATE | Required PLAN artifact before multi-file BUILD. |
| config/policy/tpa_scope_policy.json | CREATE | Governed scope policy declaring required vs optional TPA coverage. |
| contracts/schemas/tpa_scope_policy.schema.json | CREATE | Contract-first schema for TPA scope policy artifact/config. |
| contracts/examples/tpa_scope_policy.json | CREATE | Golden-path example for TPA scope policy contract. |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Add TPA certification fields and tpa_compliance check requirements. |
| contracts/examples/done_certification_record.json | MODIFY | Keep example aligned with updated done certification schema. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump done_certification_record schema version metadata. |
| spectrum_systems/modules/governance/tpa_scope_policy.py | CREATE | Deterministic policy loader and is_tpa_required(context) function. |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Add TPA compliance check, status fields, and fail-closed certification integration. |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Add promotion TPA artifact gate with reason_code=missing_tpa_artifact semantics. |
| tests/test_contracts.py | MODIFY | Validate new tpa_scope_policy contract example. |
| tests/test_done_certification.py | MODIFY | Add TPA-required PASS/FAIL/NOT_REQUIRED tests and fail-closed scope policy tests. |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Add promotion admission TPA gate tests including fail-closed policy behavior. |
| tests/test_tpa_scope_policy.py | CREATE | Add deterministic required/optional/fail-closed scope policy tests. |

## Contracts touched
- `contracts/schemas/tpa_scope_policy.schema.json` (new)
- `contracts/schemas/done_certification_record.schema.json` (version bump)
- `contracts/standards-manifest.json` (new contract registration + version metadata updates)

## Tests that must pass after execution
1. `pytest tests/test_done_certification.py tests/test_evaluation_enforcement_bridge.py tests/test_tpa_scope_policy.py tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing TPA Plan→Build→Simplify→Gate semantics.
- Do not alter unrelated promotion pathways outside done certification + enforcement bridge boundaries.
- Do not introduce prompt-level bypass logic.

## Dependencies
- Existing TPA Plan/Build/Simplify/Gate implementation (TPA-001..TPA-012) must remain authoritative.
