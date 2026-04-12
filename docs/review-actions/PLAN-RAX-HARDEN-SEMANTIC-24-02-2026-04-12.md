# Plan — RAX-HARDEN-SEMANTIC-24-02 — 2026-04-12

## Prompt type
BUILD

## Roadmap item
RAX-HARDEN-SEMANTIC-24-02

## Objective
Harden only the RAX semantic assurance layer so semantically weak, contradictory, lossy, drifted, or forged signals fail closed with explicit failure classification and evidence.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RAX-HARDEN-SEMANTIC-24-02-2026-04-12.md | CREATE | Required written plan for >2 file surgical hardening change. |
| spectrum_systems/modules/runtime/rax_model.py | MODIFY | Add semantic intent checks and normalization ambiguity signaling. |
| spectrum_systems/modules/runtime/rax_assurance.py | MODIFY | Harden input/output assurance, trace/version checks, acceptance strength, regression, evidence, and derived stop conditions. |
| tests/test_rax_interface_assurance.py | MODIFY | Add focused tests for each hardened semantic seam. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_rax_interface_assurance.py`
2. `pytest tests/test_roadmap_expansion_contracts.py`

## Scope exclusions
- Do not redesign RAX expansion architecture.
- Do not broaden to roadmap realization or unrelated modules.
- Do not modify schema contracts unless strictly required.
- Do not change ownership definitions in architecture docs.

## Dependencies
- Existing canonical ownership and role semantics in `docs/architecture/system_registry.md`.
