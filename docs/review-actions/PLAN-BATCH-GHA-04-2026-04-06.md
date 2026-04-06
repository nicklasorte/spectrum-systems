# Plan — BATCH-GHA-04 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
BATCH-GHA-04 (GHA-004)

## Objective
Add a deterministic `/roadmap-2step` PR comment entry path that produces a schema-backed two-step roadmap from repo-local source docs and routes it through the existing CDE → TLC governed continuation path.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-04-2026-04-06.md | CREATE | Required PLAN artifact before multi-file BUILD/WIRE work. |
| .github/workflows/review_trigger_pipeline.yml | MODIFY | Add `/roadmap-2step` trigger guardrails and invocation wiring. |
| spectrum_systems/modules/runtime/github_review_ingestion.py | MODIFY | Extend command marker support and emit optional roadmap artifact refs in ingestion outputs. |
| spectrum_systems/modules/runtime/github_roadmap_builder.py | CREATE | Deterministic adapter that builds exactly-two-step roadmap artifact from repo-local docs. |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Consume optional roadmap artifact and pass as continuation next-step input surface without bypassing CDE/TLC. |
| spectrum_systems/modules/runtime/github_pr_feedback.py | MODIFY | Include roadmap_id and two-line step summary in read-only feedback output. |
| contracts/schemas/roadmap_two_step_artifact.schema.json | CREATE | New authoritative contract for deterministic two-step roadmap artifact. |
| contracts/examples/roadmap_two_step_artifact.json | CREATE | Golden-path example for new roadmap two-step contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version metadata. |
| tests/test_github_roadmap_builder.py | CREATE | Deterministic and fail-closed unit coverage for roadmap builder. |
| tests/test_roadmap_trigger_pipeline.py | CREATE | Workflow-level assertions for `/roadmap-2step` command support and guardrails. |
| tests/test_github_review_ingestion.py | MODIFY | Validate ingestion support for `/roadmap-2step` marker and optional roadmap emission. |
| tests/test_github_closure_continuation.py | MODIFY | Verify roadmap artifact is fed into continuation path and CDE/TLC boundaries remain intact. |
| tests/test_github_pr_feedback.py | MODIFY | Verify PR feedback includes roadmap_id and bounded two-step summary lines. |

## Contracts touched
- `contracts/schemas/roadmap_two_step_artifact.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + contract registration)

## Tests that must pass after execution
1. `pytest tests/test_github_roadmap_builder.py tests/test_roadmap_trigger_pipeline.py tests/test_github_review_ingestion.py tests/test_github_closure_continuation.py tests/test_github_pr_feedback.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not add roadmap execution logic into GitHub trigger or roadmap builder layers.
- Do not add closure decision logic outside CDE.
- Do not bypass TLC orchestration path.
- Do not expand roadmap artifacts beyond exactly 2 steps.

## Dependencies
- Existing GHA-02/GHA-03 governed loop artifacts and contracts must remain authoritative and reusable.
