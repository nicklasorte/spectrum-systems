# Plan — RE-01 Source Authority Refresh — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-01 — Source Authority Layer initialization from structured source artifact

## Objective
Establish the smallest machine-usable source authority foundation driven by the AI Durability Strategy structured source artifact and regenerate deterministic source indexes.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/source_structured/ai_durability_strategy.source.md | CREATE | Add the seed structured source artifact consumed by the source authority layer. |
| scripts/build_source_indexes.py | MODIFY | Add repo-native parsing for `.source.md` seed artifacts and generate deterministic indexes from active structured source inputs. |
| docs/source_indexes/source_inventory.json | MODIFY | Regenerate source inventory from active source authority artifact set. |
| docs/source_indexes/obligation_index.json | MODIFY | Regenerate obligation index with machine-usable obligations from AI Durability Strategy seed artifact. |
| docs/source_indexes/component_source_map.json | MODIFY | Regenerate grounded component-to-source obligation mappings for active source authority artifact set. |
| tests/test_source_indexes_build.py | MODIFY | Align deterministic builder tests with `.source.md` seed artifact handling and duplicate-obligation enforcement logic. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_source_structured_files_validate.py`
2. `pytest tests/test_source_indexes_build.py`
3. `pytest tests/test_source_design_extraction_schema.py`
4. `python scripts/build_source_indexes.py`

## Scope exclusions
- Do not modify roadmap authority documents.
- Do not add runtime/module behavior.
- Do not redesign source extraction JSON schema contracts.
- Do not fabricate additional structured source artifacts beyond the AI Durability Strategy seed.

## Dependencies
- Existing source authority layer foundations from `PLAN-SOURCE-AUTHORITY-LAYER-2026-03-28.md`.
