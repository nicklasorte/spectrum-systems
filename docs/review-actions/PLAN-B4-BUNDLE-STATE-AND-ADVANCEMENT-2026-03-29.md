# Plan — B4 Machine-Enforced Bundle State + Advancement Contracts — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B4 — Machine-Enforced Bundle State + Advancement Contracts

## Objective
Add a schema-bound, deterministic PQX bundle-state substrate that enforces ordered step/bundle advancement and integrates with current PQX runtime seams without introducing a separate orchestration framework.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-B4-BUNDLE-STATE-AND-ADVANCEMENT-2026-03-29.md | CREATE | Required plan artifact before multi-file BUILD scope. |
| docs/review-actions/B4_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Required execution summary/review artifact for this slice. |
| docs/roadmaps/pqx_bundle_state.md | CREATE | Bundle-state contract/runtime behavior documentation for operators and reviewers. |
| contracts/schemas/pqx_bundle_state.schema.json | CREATE | Canonical schema for persisted machine-enforced bundle execution state. |
| contracts/examples/pqx_bundle_state.json | CREATE | Golden-path example payload for pqx_bundle_state validation and fixture use. |
| contracts/standards-manifest.json | MODIFY | Register pqx_bundle_state contract and bump manifest version metadata. |
| spectrum_systems/modules/runtime/pqx_bundle_state.py | CREATE | Deterministic bundle-state load/validate/advance/block/review/fix helpers. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Wire optional persisted bundle-state initialization/advancement into existing sequence runner seam. |
| spectrum_systems/modules/runtime/__init__.py | MODIFY | Export new bundle-state helpers for repo-native runtime usage. |
| tests/test_pqx_bundle_state.py | CREATE | Focused runtime tests for initialization, advancement, blocking, duplicate prevention, review/fix shape validation, and resume derivation. |
| tests/test_pqx_sequence_runner.py | MODIFY | Integration coverage for sequence-runner + bundle-state wiring and fail-closed behavior. |
| tests/test_contracts.py | MODIFY | Ensure new pqx_bundle_state example validates via contract tests. |

## Contracts touched
- CREATE `contracts/schemas/pqx_bundle_state.schema.json` (`schema_version` = `1.0.0`).
- MODIFY `contracts/standards-manifest.json` to add `pqx_bundle_state` contract entry and publication metadata bump.

## Tests that must pass after execution
1. `pytest tests/test_pqx_bundle_state.py tests/test_pqx_sequence_runner.py tests/test_pqx_backbone.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-B4-BUNDLE-STATE-AND-ADVANCEMENT-2026-03-29.md`
5. `pytest`

## Scope exclusions
- Do not build a full autonomous multi-bundle executor.
- Do not redesign roadmap parsing or authority resolution semantics.
- Do not add network/LLM behavior.
- Do not refactor unrelated runtime or prompt-queue modules.

## Dependencies
- B1/B2 roadmap authority bridge and compatibility mirror enforcement must remain intact.
- Existing `prompt_queue_sequence_run` seam remains the active execution path; bundle-state integration is additive and fail-closed.
