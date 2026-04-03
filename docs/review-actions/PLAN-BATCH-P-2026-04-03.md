# Plan — BATCH-P — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-P — PRG: Program Layer Integration

## Objective
Introduce a governed program direction layer that deterministically constrains roadmap generation and eligibility decisions without overriding existing control authority.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-P-2026-04-03.md | CREATE | Plan-first artifact required before multi-file BUILD work. |
| contracts/schemas/program_artifact.schema.json | CREATE | Define governed program contract. |
| contracts/examples/program_artifact.json | CREATE | Golden-path example for program contract. |
| contracts/schemas/program_progress.schema.json | CREATE | Define deterministic program progress artifact contract. |
| contracts/examples/program_progress.json | CREATE | Golden-path example for program progress contract. |
| contracts/standards-manifest.json | MODIFY | Register/version new program-layer contracts and related schema bumps. |
| spectrum_systems/modules/runtime/program_layer.py | CREATE | Implement deterministic batch mapping, roadmap constraints, and progress model. |
| spectrum_systems/modules/runtime/review_roadmap_generator.py | MODIFY | Make MAP generation program-aware and constrained. |
| spectrum_systems/orchestration/roadmap_eligibility.py | MODIFY | Emit program compliance signal with freeze/block behavior. |
| contracts/schemas/roadmap_eligibility_artifact.schema.json | MODIFY | Add program compliance fields to eligibility contract. |
| contracts/examples/roadmap_eligibility_artifact.json | MODIFY | Keep roadmap eligibility example in sync with schema updates. |
| tests/test_program_layer.py | CREATE | Add tests for mapping, MAP filtering, and deterministic progress. |
| tests/test_roadmap_generator.py | CREATE | Add dedicated MAP generator program-constraint tests. |
| tests/test_roadmap_eligibility.py | MODIFY | Add program violation detection tests. |
| tests/test_contracts.py | MODIFY | Validate new program contracts/examples. |
| docs/roadmaps/roadmap_generator_authority.md | MODIFY | Document program-first constrained flow sequencing through review/eval/control/MAP/RDX. |

## Contracts touched
- Create `program_artifact` (v1.0.0).
- Create `program_progress` (v1.0.0).
- Modify `roadmap_eligibility_artifact` (bump to v1.2.0) to include program compliance signals.

## Tests that must pass after execution
1. `pytest tests/test_program_layer.py`
2. `pytest tests/test_roadmap_generator.py`
3. `pytest tests/test_roadmap_eligibility.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change roadmap authority source files or checkpoint definitions.
- Do not alter PQX executor behavior beyond eligibility signaling.
- Do not introduce autonomous execution loops or control overrides.

## Dependencies
- Existing governed roadmap and eligibility contracts must remain authoritative execution gates.
- Program layer must remain directional only and subordinate to eval/control decisions.
