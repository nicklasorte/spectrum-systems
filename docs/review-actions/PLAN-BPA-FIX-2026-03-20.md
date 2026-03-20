# Plan — Prompt BPA Fixes (CI + Registry + Contract Hardening) — 2026-03-20

## Prompt type
PLAN

## Roadmap item
Prompt BPA — Strategic Knowledge Layer Foundation (stabilization)

## Objective
Fix CI failures by hardening strategic contract tests, removing network-prone schema references, restoring manifest/registry consistency, and adding bootstrap manifest/schema integrity coverage.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BPA-FIX-2026-03-20.md | CREATE | Required plan before multi-file stabilization build. |
| PLANS.md | MODIFY | Register active BPA fix plan. |
| requirements-dev.txt | MODIFY | Ensure deterministic test dependencies include contract validation dependencies. |
| contracts/standards-manifest.json | MODIFY | Repair ecosystem registry compatibility for intended consumers and strategic entries. |
| contracts/schemas/book_intelligence_pack.schema.json | MODIFY | Remove external $ref dependency and keep strict fail-closed validation. |
| contracts/schemas/transcript_intelligence_pack.schema.json | MODIFY | Remove external $ref dependency and keep strict fail-closed validation. |
| contracts/schemas/story_bank_entry.schema.json | MODIFY | Remove external $ref dependency and keep strict fail-closed validation. |
| contracts/schemas/tactic_register.schema.json | MODIFY | Remove external $ref dependency and keep strict fail-closed validation. |
| contracts/schemas/viewpoint_pack.schema.json | MODIFY | Remove external $ref dependency and keep strict fail-closed validation. |
| contracts/schemas/evidence_map.schema.json | MODIFY | Remove external $ref dependency and keep strict fail-closed validation. |
| tests/test_strategic_knowledge_schemas.py | MODIFY | Remove silent skip pattern; strengthen contract coverage across new schema family. |
| tests/test_contract_bootstrap.py | CREATE | Add manifest/schema bootstrap integrity checks. |

## Contracts touched
- book_intelligence_pack
- transcript_intelligence_pack
- story_bank_entry
- tactic_register
- viewpoint_pack
- evidence_map
- standards manifest strategic contract registry entries

## Tests that must pass after execution
1. `pytest tests/test_strategic_knowledge_schemas.py tests/test_contract_bootstrap.py tests/test_strategic_knowledge_catalog.py tests/test_strategic_knowledge_pathing.py`
2. `python scripts/validate_ecosystem_registry.py`
3. `pytest tests/test_ecosystem_registry.py`
4. `python scripts/run_contract_enforcement.py`
5. `PLAN_FILES="docs/review-actions/PLAN-BPA-FIX-2026-03-20.md PLANS.md requirements-dev.txt contracts/standards-manifest.json contracts/schemas/book_intelligence_pack.schema.json contracts/schemas/transcript_intelligence_pack.schema.json contracts/schemas/story_bank_entry.schema.json contracts/schemas/tactic_register.schema.json contracts/schemas/viewpoint_pack.schema.json contracts/schemas/evidence_map.schema.json tests/test_strategic_knowledge_schemas.py tests/test_contract_bootstrap.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement extraction logic.
- Do not alter strategic source/artifact schema contracts beyond compatibility and strictness-preserving reference design.
- Do not modify ecosystem registry contents unless strictly required.

## Dependencies
- Prior BPA foundation commit present on branch.
