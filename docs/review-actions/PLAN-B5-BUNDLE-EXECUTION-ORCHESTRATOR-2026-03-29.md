# Plan — B5 Bundle Execution Orchestrator — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B5 — Bundle Execution Orchestrator

## Objective
Implement a deterministic, fail-closed bundle execution orchestrator that resolves bundle definitions from `execution_bundles.md`, validates roadmap-coupled ordering/dependencies, executes via existing PQX sequence seams, persists governed bundle state, supports resume, and emits a schema-bound bundle execution artifact.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-B5-BUNDLE-EXECUTION-ORCHESTRATOR-2026-03-29.md | CREATE | Required pre-build plan artifact declaring scope. |
| docs/review-actions/B5_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Required post-build execution summary/evidence artifact. |
| docs/roadmaps/execution_bundles.md | MODIFY | Add deterministic executable bundle table section consumed by machine parser. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | CREATE | New runtime orchestrator module implementing bundle parsing, validation, execution, resume, and artifact emission. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Narrow additive integration path enabling bundle invocation via orchestrator while preserving existing single-step behavior. |
| scripts/run_pqx_bundle.py | CREATE | Thin deterministic local CLI entrypoint for bundle execution. |
| contracts/schemas/pqx_bundle_execution_record.schema.json | CREATE | New governed contract for bundle execution outputs. |
| contracts/examples/pqx_bundle_execution_record.json | CREATE | Golden-path example artifact for new contract. |
| contracts/standards-manifest.json | MODIFY | Register new artifact contract and bump manifest version metadata. |
| docs/roadmaps/pqx_bundle_orchestrator.md | CREATE | Operator/developer documentation for orchestrator behavior and failure semantics. |
| tests/test_pqx_bundle_orchestrator.py | CREATE | Focused fail-closed tests for bundle resolution, validation, execution, failure handling, and resume safety. |
| tests/test_pqx_sequence_runner.py | MODIFY | Add narrow integration coverage for bundle invocation path compatibility. |
| tests/test_contracts.py | MODIFY | Add contract validation coverage for `pqx_bundle_execution_record`. |

## Contracts touched
- Create `contracts/schemas/pqx_bundle_execution_record.schema.json`.
- Register `pqx_bundle_execution_record` in `contracts/standards-manifest.json`.
- Create `contracts/examples/pqx_bundle_execution_record.json`.

## Tests that must pass after execution
1. `pytest tests/test_pqx_bundle_orchestrator.py`
2. `pytest tests/test_pqx_sequence_runner.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_pqx_backbone.py`
5. `pytest tests/test_roadmap_authority.py tests/test_roadmap_tracker.py`
6. `pytest`
7. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-B5-BUNDLE-EXECUTION-ORCHESTRATOR-2026-03-29.md`

## Scope exclusions
- Do not redesign roadmap authority resolution logic.
- Do not introduce networked services, autonomous review branching, or non-deterministic execution behavior.
- Do not replace existing PQX backbone/sequence execution systems.
- Do not modify unrelated roadmap rows or broaden execution bundle semantics beyond strict parser hardening needed for safe machine execution.

## Dependencies
- RM-01 and RM-02 authority/state foundations must remain intact.
- B4 bundle-state runtime helper contract remains source-of-truth for persisted advancement semantics.
- Existing PQX sequence runner continuity invariants remain authoritative.
