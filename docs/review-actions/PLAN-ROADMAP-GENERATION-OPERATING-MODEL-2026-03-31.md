# Plan — ROADMAP-GENERATION-OPERATING-MODEL — 2026-03-31

## Prompt type
PLAN

## Roadmap item
Roadmap authority refresh + source obligation gap scan + compatibility-preserving roadmap update

## Objective
Run the governed roadmap-generation operating model end-to-end using structured source indexes and repo evidence, then save an updated active roadmap authority + compatibility mirror without breaking machine/runtime parsing surfaces.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ROADMAP-GENERATION-OPERATING-MODEL-2026-03-31.md | CREATE | Required plan artifact before multi-file governance/doc updates. |
| PLANS.md | MODIFY | Register the new active plan in the plan inventory table. |
| docs/source_indexes/source_inventory.json | MODIFY | Refresh deterministic source authority inventory from structured source artifacts. |
| docs/source_indexes/obligation_index.json | MODIFY | Refresh deterministic obligation index for machine-usable obligation surface. |
| docs/source_indexes/component_source_map.json | MODIFY | Refresh deterministic component-source mapping index. |
| docs/roadmaps/system_roadmap.md | MODIFY | Save next authority update with explicit source-index-informed bottleneck and gate posture. |
| docs/roadmap/system_roadmap.md | MODIFY | Keep compatibility mirror coherent with authority update while preserving legacy executable IDs and parser shape. |
| docs/roadmaps/execution_state_inventory.md | MODIFY | Record refreshed source-obligation gap scan findings in repo-native inventory surface. |
| docs/reviews/2026-03-31-roadmap-generation-delivery-report.md | CREATE | Persist run delivery report artifact for strategic review handoff. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_source_structured_files_validate.py tests/test_source_indexes_build.py`
2. `pytest tests/test_roadmap_authority.py tests/test_roadmap_step_contract.py tests/test_roadmap_tracker.py`
3. `pytest tests/test_pqx_backbone.py tests/test_pqx_bundle_orchestrator.py tests/test_pqx_sequence_runner.py tests/test_pqx_slice_runner.py`
4. `pytest tests/test_prompt_queue_sequence_cli.py tests/test_run_pqx_bundle_cli.py`
5. `python scripts/check_roadmap_authority.py`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify runtime/orchestration Python implementation modules.
- Do not modify contracts/schemas or standards manifest version pins.
- Do not remove or rename legacy executable compatibility IDs in `docs/roadmap/system_roadmap.md`.
- Do not claim true closed-loop MVP unless evidence in current repo run proves automated measurable learning-loop authority.

## Dependencies
- `docs/roadmaps/roadmap_authority.md` bridge semantics remain authoritative.
- `scripts/build_source_indexes.py` deterministic generation logic remains source of truth for source indexes.
- Existing roadmap parser/runtime tests remain the machine-compatibility gate.
