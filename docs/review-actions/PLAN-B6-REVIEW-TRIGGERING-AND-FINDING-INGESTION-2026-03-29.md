# Plan — B6 Review Triggering + Finding Ingestion + Pending-Fix Wiring — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B6 — Review Triggering + Finding Ingestion + Pending-Fix Wiring

## Objective
Implement deterministic, fail-closed review checkpoint enforcement and finding-to-pending-fix ingestion in PQX bundle execution while preserving existing non-review bundle behavior.

## Motivation
Bundle execution currently supports deterministic step ordering and fail-closed step blocking, but required review checkpoints and structured finding ingestion are not machine-enforced end-to-end. This slice closes that gap by adding a strict review artifact contract, state wiring for unresolved review gates and pending fixes, and orchestrator/CLI enforcement that blocks continuation until required review obligations are satisfied.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| `contracts/schemas/pqx_review_result.schema.json` | CREATE | Add strict governed review artifact schema for bundle review ingestion. |
| `contracts/examples/pqx_review_result.json` | CREATE | Add deterministic golden-path example review artifact. |
| `contracts/schemas/pqx_bundle_state.schema.json` | MODIFY | Add review checkpoint requirements, gate state, and first-class pending-fix shape. |
| `contracts/schemas/pqx_bundle_execution_record.schema.json` | MODIFY | Add governed review block metadata and attached review references. |
| `contracts/examples/pqx_bundle_state.json` | MODIFY | Align example with new review checkpoint and pending-fix fields. |
| `contracts/examples/pqx_bundle_execution_record.json` | MODIFY | Align example with review-block metadata fields. |
| `contracts/standards-manifest.json` | MODIFY | Register new contract and version-bump updated contracts per contract-first governance. |
| `spectrum_systems/modules/runtime/pqx_bundle_state.py` | MODIFY | Add deterministic review requirement model, review artifact ingestion, and gate enforcement helpers. |
| `spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py` | MODIFY | Parse review checkpoints from bundle plan and enforce review gating during run/resume. |
| `scripts/run_pqx_bundle.py` | MODIFY | Add thin CLI commands for run/until-checkpoint, attach-review, ingest-findings, and resume. |
| `docs/roadmaps/execution_bundles.md` | MODIFY | Add machine-readable review checkpoint table and operator notes for B6 behavior. |
| `docs/roadmaps/pqx_bundle_orchestrator.md` | MODIFY | Document deterministic review/fix loop behavior and failure modes. |
| `docs/review-actions/B6_EXECUTION_SUMMARY_2026-03-29.md` | CREATE | Operator-focused execution summary and usage notes for B6. |
| `tests/test_pqx_bundle_state.py` | MODIFY | Add review checkpoint, artifact ingestion, duplicate/conflict, and replay persistence tests. |
| `tests/test_pqx_bundle_orchestrator.py` | MODIFY | Add orchestrator review enforcement and fail-closed resume tests. |
| `tests/test_contracts.py` | MODIFY | Validate new pqx_review_result contract example. |

## Contracts touched
- `pqx_review_result` (new, schema_version `1.0.0`).
- `pqx_bundle_state` (additive schema update; version bump required).
- `pqx_bundle_execution_record` (additive schema update; version bump required).
- `contracts/standards-manifest.json` (artifact registry/version updates).

## Invariants to preserve
- Existing single-step PQX backbone flows remain unchanged.
- Existing bundle happy path without required review remains completed and deterministic.
- No network calls, no LLM calls, no nondeterministic branching.
- Bundle step ordering/dependency fail-closed behavior remains intact.

## Tests that must pass after execution
1. `pytest tests/test_pqx_bundle_state.py tests/test_pqx_bundle_orchestrator.py tests/test_contracts.py`
2. `pytest tests/test_pqx_sequence_runner.py`
3. `pytest tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement autonomous fix generation.
- Do not mutate roadmap execution rows dynamically.
- Do not add heuristic ranking beyond deterministic severity/priority mapping.
- Do not introduce multi-bundle parallel scheduling.
- Do not add external review service integrations.

## Dependencies
- Active roadmap authority remains `docs/roadmaps/system_roadmap.md`.
- Existing PQX bundle state and orchestrator seams from B4/B5 remain the implementation base.
