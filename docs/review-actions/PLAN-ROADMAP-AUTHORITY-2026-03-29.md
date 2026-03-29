# Plan — System Roadmap Step 2 Authority Integration — 2026-03-29

## Prompt type
PLAN

## Roadmap item
SYSTEM ROADMAP — STEP 2: AUTHORITY + REPO INTEGRATION

## Objective
Install `docs/roadmap/system_roadmap.md` as the single authoritative roadmap reference and enforce this authority with repository docs, CI validation, and tests.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ROADMAP-AUTHORITY-2026-03-29.md | CREATE | Required written plan before multi-file governance/build updates |
| docs/roadmap/system_roadmap.md | MODIFY | Ensure required Step 2 header + authority note and canonical roadmap content |
| docs/roadmap/README.md | CREATE | Add roadmap authority index |
| docs/roadmap/pqx_execution_map.md | CREATE | Map PQX slices to system roadmap steps |
| docs/roadmaps/system_roadmap.md | MODIFY | Mark as subordinate and redirect authority |
| docs/roadmaps/codex-prompt-roadmap.md | MODIFY | Mark as subordinate and remove primary authority implication |
| docs/roadmaps/operational-ai-systems-roadmap.md | MODIFY | Mark as subordinate |
| docs/roadmap/pqx_protocol_hardening.md | MODIFY | Mark as subordinate |
| docs/roadmap/pqx_queue_roadmap.md | MODIFY | Mark as subordinate |
| docs/roadmap/trust_hardening_roadmap.md | MODIFY | Mark as subordinate |
| docs/roadmap/roadmap_step_contract.md | MODIFY | Mark as subordinate |
| docs/roadmap.md | MODIFY | Replace deprecated target with authoritative roadmap path |
| AGENTS.md | MODIFY | Update ACTIVE roadmap path references |
| CODEX.md | MODIFY | Update ACTIVE roadmap path references |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Point parser/request metadata to authoritative roadmap path |
| scripts/pqx_runner.py | MODIFY | Default roadmap path to authoritative roadmap |
| scripts/check_roadmap_authority.py | CREATE | Add CI authority guardrail |
| tests/test_pqx_backbone.py | MODIFY | Align roadmap path assertion |
| tests/test_roadmap_authority.py | CREATE | Validate roadmap authority invariants |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_authority.py tests/test_pqx_backbone.py`
2. `python scripts/check_roadmap_authority.py`

## Scope exclusions
- Do not alter roadmap table row semantics beyond required authority wrappers/redirects.
- Do not refactor unrelated runtime modules or contract schemas.
- Do not remove legacy roadmap/history files; mark subordinate only.

## Dependencies
- Existing completed system roadmap content in `docs/roadmaps/system_roadmap.md` must remain intact when transferred under the new Step 2 authority header.
