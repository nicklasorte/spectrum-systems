# Plan — SOURCE-AUTHORITY-LAYER — 2026-03-28

## Prompt type
PLAN

## Roadmap item
ACTIVE roadmap support slice — governed source-ingestion layer for roadmap generation and architecture reconstruction.

## Objective
Implement a deterministic, schema-first source authority layer that converts raw source PDFs into governed structured JSON and builds reproducible indexes for source and obligation traceability.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/source_design_extraction.schema.json | CREATE | Canonical schema for structured source extraction artifacts |
| docs/source_raw/.gitkeep | CREATE | Ensure raw source directory is tracked when PDFs are unavailable in this environment |
| docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json | CREATE | Structured extraction starter artifact for source PDF |
| docs/source_structured/production_ready_best_practices_for_integrating_ai_models_into_automated_engineering_workflows.json | CREATE | Structured extraction starter artifact for source PDF |
| docs/source_structured/spectrum_systems_build_governance_engine_sbge_design.json | CREATE | Structured extraction starter artifact for source PDF |
| docs/source_structured/agent_eval_integration_design_spectrum_systems.json | CREATE | Structured extraction starter artifact for source PDF |
| docs/source_structured/spectrum_systems_ai_integration_governed_api_adapter_design.json | CREATE | Structured extraction starter artifact for source PDF |
| docs/source_structured/spectrum_systems_done_certification_gate_gov10_design.json | CREATE | Structured extraction starter artifact for source PDF |
| docs/source_indexes/source_inventory.json | CREATE | Deterministic source inventory index |
| docs/source_indexes/obligation_index.json | CREATE | Deterministic obligation traceability index |
| docs/source_indexes/component_source_map.json | CREATE | Deterministic component-to-source mapping index |
| scripts/build_source_indexes.py | CREATE | Deterministic schema-validation and index build utility |
| tests/test_source_design_extraction_schema.py | CREATE | Schema contract tests and negative validation cases |
| tests/test_source_indexes_build.py | CREATE | Index builder behavior and deterministic output tests |
| tests/test_source_structured_files_validate.py | CREATE | Structured source files contract compliance tests |
| docs/architecture/source_authority_layer.md | CREATE | Governance documentation for source authority usage in roadmap prompts |
| docs/review-actions/PLAN-SOURCE-AUTHORITY-LAYER-2026-03-28.md | CREATE | Required written execution plan prior to build |

## Contracts touched
- Create `contracts/schemas/source_design_extraction.schema.json`.
- No changes to existing contract files.

## Tests that must pass after execution
1. `pytest tests/test_source_design_extraction_schema.py`
2. `pytest tests/test_source_structured_files_validate.py`
3. `pytest tests/test_source_indexes_build.py`

## Scope exclusions
- Do not modify unrelated schemas, modules, or governance automation.
- Do not parse PDF contents automatically in this slice.
- Do not add third-party dependencies beyond existing repository requirements.
- Do not alter roadmap files outside this plan artifact.

## Dependencies
- `docs/vision.md` reviewed before structural changes.
- Root + scoped AGENTS instructions for `contracts/`, `scripts/`, and `tests/` applied.
