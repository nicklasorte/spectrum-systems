# Plan — BATCH-AEX — 2026-04-08

## Prompt type
PLAN

## Roadmap item
BATCH-AEX

## Objective
Introduce AEX as the canonical admission boundary for repo-mutating Codex execution requests, wire TLC/PQX fail-closed admission checks, and publish matching contracts/tests/docs.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/architecture/system_registry.md | MODIFY | Add AEX system definition, entry invariants, graph updates, and boundary clarifications. |
| docs/architecture/foundation_pqx_eval_control.md | MODIFY | Extend foundation flow to include admission boundary and required admission artifacts. |
| docs/architecture/strategy-control.md | MODIFY | Minimal strategy update for no alternate write paths through AEX admission. |
| contracts/schemas/build_admission_record.schema.json | CREATE | Canonical schema for AEX admission decisions. |
| contracts/schemas/normalized_execution_request.schema.json | CREATE | Canonical schema for normalized request artifact emitted by AEX. |
| contracts/schemas/admission_rejection_record.schema.json | CREATE | Canonical schema for fail-closed AEX rejection artifact. |
| contracts/examples/build_admission_record.example.json | CREATE | Golden-path example for build_admission_record. |
| contracts/examples/normalized_execution_request.example.json | CREATE | Golden-path example for normalized_execution_request. |
| contracts/examples/admission_rejection_record.example.json | CREATE | Golden-path example for admission_rejection_record. |
| contracts/standards-manifest.json | MODIFY | Register new contracts with version metadata. |
| spectrum_systems/aex/__init__.py | CREATE | Public AEX exports. |
| spectrum_systems/aex/errors.py | CREATE | AEX error types and reason-code declarations. |
| spectrum_systems/aex/classifier.py | CREATE | Deterministic execution classification rules. |
| spectrum_systems/aex/models.py | CREATE | Typed AEX request/response models. |
| spectrum_systems/aex/engine.py | CREATE | AEX admission engine with fail-closed behavior. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Enforce AEX admission requirement for repo-mutating TLC/PQX path. |
| contracts/examples/system_registry_artifact.json | MODIFY | Keep machine-readable registry aligned with AEX ownership and interactions. |
| tests/test_system_registry_boundaries.py | MODIFY | Assert AEX boundary edges and ownership invariants. |
| tests/test_aex_schema_validation.py | CREATE | Validate AEX schemas including additionalProperties fail-closed behavior. |
| tests/test_aex_admission.py | CREATE | Validate accepted/rejected/ambiguous admission behavior and trace continuity. |
| tests/test_aex_fail_closed.py | CREATE | Validate unknown/underspecified requests fail closed with rejection artifacts. |
| tests/test_tlc_requires_admission_for_repo_write.py | CREATE | Validate TLC/PQX reject repo-write requests without admission artifacts. |

## Contracts touched
- `build_admission_record` (new)
- `normalized_execution_request` (new)
- `admission_rejection_record` (new)
- `contracts/standards-manifest.json` version metadata update (additive contract registration)

## Tests that must pass after execution
1. `pytest tests/test_aex_schema_validation.py tests/test_aex_admission.py tests/test_aex_fail_closed.py tests/test_tlc_requires_admission_for_repo_write.py`
2. `pytest tests/test_system_registry_boundaries.py tests/test_contracts.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign TLC orchestration state machine beyond admission guard wiring.
- Do not alter TPA trust/policy decision semantics.
- Do not alter PQX execution internals beyond admission precondition enforcement.
- Do not perform unrelated refactors in prompt queue, roadmap, or governance modules.

## Dependencies
- Existing `system_registry_artifact` runtime enforcement remains authoritative and is extended, not replaced.
