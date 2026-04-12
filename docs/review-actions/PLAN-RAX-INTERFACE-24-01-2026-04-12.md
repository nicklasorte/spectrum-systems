# Plan — RAX-INTERFACE-24-01 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
RAX-INTERFACE-24-01

## Objective
Implement a strict, deterministic RAX interface + assurance subsystem that validates compact upstream roadmap input, deterministically expands to downstream roadmap step contracts, and emits a fail-closed assurance audit artifact.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/rax_upstream_input_envelope.schema.json | CREATE | Canonical upstream input contract for RAX compact roadmap intake. |
| contracts/examples/rax_upstream_input_envelope.example.json | CREATE | Deterministic valid upstream envelope example. |
| contracts/schemas/roadmap_step_contract.schema.json | MODIFY | Tighten downstream output contract strictness and compatibility requirements. |
| contracts/examples/roadmap_step_contract.example.json | MODIFY | Keep downstream example aligned with tightened contract. |
| contracts/schemas/rax_assurance_audit_record.schema.json | CREATE | Canonical assurance audit artifact schema for RAX decision outcomes. |
| contracts/examples/rax_assurance_audit_record.example.json | CREATE | Deterministic valid assurance audit example. |
| contracts/standards-manifest.json | MODIFY | Register new/updated contract versions in authoritative manifest. |
| config/roadmap_expansion_policy.json | MODIFY | Bind deterministic translation defaults and templates used by RAX expansion. |
| spectrum_systems/modules/runtime/rax_model.py | CREATE | Canonical internal model load/normalize/validate logic. |
| spectrum_systems/modules/runtime/rax_expander.py | CREATE | Deterministic expansion from canonical model to downstream step contract + trace. |
| spectrum_systems/modules/runtime/rax_assurance.py | CREATE | Input/output/downstream compatibility assurance and local decision classification. |
| tests/test_roadmap_expansion_contracts.py | MODIFY | Add/extend strict contract-level checks for upstream/downstream schemas and policy coupling. |
| tests/test_rax_interface_assurance.py | CREATE | Focused deterministic tests for model normalization, expansion determinism, and assurance fail-closed behavior. |

## Contracts touched
- Add `rax_upstream_input_envelope` schema + example.
- Tighten `roadmap_step_contract` schema + example.
- Add `rax_assurance_audit_record` schema + example.
- Update `contracts/standards-manifest.json` versions for touched contracts.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_expansion_contracts.py tests/test_rax_interface_assurance.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement broad RF-02/RF-03 realization logic beyond RAX interface/assurance wiring.
- Do not add prioritization, sequencing, readiness, or promotion authority to RAX.
- Do not infer missing critical fields or add permissive fallback behavior.
- Do not refactor unrelated runtime modules or governance surfaces.

## Dependencies
- Existing roadmap expansion contracts and policy baseline (`roadmap_step_contract`, `roadmap_expansion_trace`, `config/roadmap_expansion_policy.json`) remain canonical dependencies.
