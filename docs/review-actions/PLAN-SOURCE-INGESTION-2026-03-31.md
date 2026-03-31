# Plan — SOURCE-INGESTION — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-01 source authority indexing expansion (source-ingestion slice)

## Objective
Create one `.source.md` structured artifact per remaining PDF in `docs/source_raw/`, regenerate source indexes, and validate source/index build behavior without changing runtime logic.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SOURCE-INGESTION-2026-03-31.md | CREATE | Plan-first artifact required for multi-file ingestion change. |
| PLANS.md | MODIFY | Register active plan in repository plan ledger. |
| docs/source_structured/agent_eval_integration_design.source.md | CREATE | Structured source artifact for `docs/source_raw/agent_eval_integration_design.pdf`. |
| docs/source_structured/done_certification_gate_gov10.source.md | CREATE | Structured source artifact for `docs/source_raw/done_certification_gate_gov10.pdf`. |
| docs/source_structured/google_sre_mapping.source.md | CREATE | Structured source artifact for `docs/source_raw/google_sre_mapping.pdf`. |
| docs/source_structured/governed_api_adapter_design.source.md | CREATE | Structured source artifact for `docs/source_raw/governed_api_adapter_design.pdf`. |
| docs/source_structured/judgment_capture_reuse_system_design.source.md | CREATE | Structured source artifact for `docs/source_raw/judgment_capture_reuse_system_design.pdf`. |
| docs/source_structured/production_ai_workflow_best_practices.source.md | CREATE | Structured source artifact for `docs/source_raw/production_ai_workflow_best_practices.pdf`. |
| docs/source_structured/sbge_design.source.md | CREATE | Structured source artifact for `docs/source_raw/sbge_design.pdf`. |
| docs/source_indexes/source_inventory.json | MODIFY | Regenerated source inventory output from source index builder. |
| docs/source_indexes/obligation_index.json | MODIFY | Regenerated obligation index output from source index builder. |
| docs/source_indexes/component_source_map.json | MODIFY | Regenerated component/source mapping output from source index builder. |
| tests/test_source_indexes_build.py | MODIFY | Align deterministic index test expectations with expanded markdown source ingestion surface. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/build_source_indexes.py`
2. `pytest tests/test_source_structured_files_validate.py`
3. `pytest tests/test_source_indexes_build.py`
4. `pytest tests/test_source_design_extraction_schema.py`

## Scope exclusions
- Do not modify runtime modules or orchestration logic.
- Do not change roadmap authority files other than plan registration in `PLANS.md`.
- Do not add speculative obligations that are not directly grounded in parseable source content.
- Do not modify existing JSON schema contracts.

## Dependencies
- Existing source index builder (`scripts/build_source_indexes.py`) and current `.source.md` ingestion pattern must remain authoritative.
