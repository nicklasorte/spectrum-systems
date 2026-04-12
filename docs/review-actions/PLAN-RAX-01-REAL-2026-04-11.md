# Plan — RAX-01-REAL — 2026-04-11

## Prompt type
BUILD

## Roadmap item
RAX-01-REAL

## Objective
Establish a strict, fail-closed contract and policy foundation for roadmap step expansion by adding schemas, deterministic policy config, examples, manifest registration, and focused validation tests.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/roadmap_step_contract.schema.json | CREATE | Define strict enriched roadmap step contract schema. |
| contracts/schemas/roadmap_expansion_trace.schema.json | CREATE | Define strict deterministic expansion trace schema. |
| contracts/examples/roadmap_step_contract.example.json | CREATE | Provide a realistic valid example payload for schema validation. |
| contracts/examples/roadmap_expansion_trace.example.json | CREATE | Provide a realistic valid expansion trace example payload. |
| config/roadmap_expansion_policy.json | CREATE | Add deterministic mapping/config-only expansion policy foundation. |
| contracts/standards-manifest.json | MODIFY | Register the new contract artifacts and bump standards/source versions. |
| tests/test_roadmap_expansion_contracts.py | CREATE | Add schema + policy validation tests covering success/failure cases. |

## Contracts touched
- roadmap_step_contract (new)
- roadmap_expansion_trace (new)
- standards_manifest (version metadata + new contract registrations)

## Tests that must pass after execution
1. `pytest tests/test_roadmap_expansion_contracts.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement roadmap realization/execution runtime logic.
- Do not modify RF-02 or RF-03 production artifacts beyond schema examples.
- Do not introduce LLM inference behavior or policy authority logic.
- Do not perform unrelated refactors.

## Dependencies
- Existing canonical ownership roles in `docs/architecture/system_registry.md` must remain authoritative.
