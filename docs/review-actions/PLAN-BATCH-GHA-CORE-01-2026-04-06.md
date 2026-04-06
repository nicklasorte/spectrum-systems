# Plan — BATCH-GHA-CORE-01 / GHA-CORE-001 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
GHA-CORE-001 — Autonomous Governed PR Loop Hardening

## Objective
Harden GHA-01/GHA-02 trigger routing and runtime adapters so governed continuation is deterministic, fail-closed, terminal-state bounded, and branch-mutation policy explicit without moving decision authority into workflows.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-CORE-01-2026-04-06.md | CREATE | Required PLAN artifact before multi-file BUILD/WIRE changes |
| .github/workflows/review_trigger_pipeline.yml | MODIFY | Tighten trigger guards and publish deterministic handoff artifact/index |
| .github/workflows/closure_continuation_pipeline.yml | MODIFY | Consume deterministic handoff surface, terminal-state stop handling, idempotent status comment behavior, explicit branch-update policy notes |
| spectrum_systems/modules/runtime/github_review_ingestion.py | MODIFY | Emit deterministic github_review_handoff_artifact and fail-closed trigger normalization support |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Consume handoff artifact only, enforce terminal-state constraints, enforce explicit branch update allow/deny summary flags |
| spectrum_systems/modules/runtime/github_pr_feedback.py | MODIFY | Preserve read-only idempotent comment payload shape with deterministic artifact refs |
| contracts/schemas/github_review_handoff_artifact.schema.json | CREATE | Contract-first addition for deterministic GHA-01→GHA-02 handoff |
| contracts/examples/github_review_handoff_artifact.json | CREATE | Golden-path handoff example |
| contracts/standards-manifest.json | MODIFY | Register/pin new handoff contract version |
| tests/test_github_review_handoff.py | CREATE | Validate handoff artifact schema + deterministic creation/consumption |
| tests/test_github_closure_continuation.py | MODIFY | Add coverage for handoff-only consumption and branch-update policy/terminal behavior |
| tests/test_github_review_ingestion.py | MODIFY | Assert handoff artifact emission and schema validation in GHA-01 outputs |
| tests/test_review_trigger_pipeline_workflow.py | MODIFY | Assert tightened trigger guards and handoff artifact publication |
| tests/test_closure_continuation_pipeline_workflow.py | MODIFY | Assert handoff-only intake, explicit terminal stop behavior, and guarded comment update path |
| tests/test_github_pr_feedback.py | MODIFY | Strengthen idempotent read-only feedback assertions |
| tests/test_contracts.py | MODIFY | Add contract example/schema validation coverage for github_review_handoff_artifact |

## Contracts touched
- Create `github_review_handoff_artifact` schema and example.
- Update `contracts/standards-manifest.json` version and contract registry entry for the new artifact type.

## Tests that must pass after execution
1. `pytest tests/test_github_review_ingestion.py tests/test_github_review_handoff.py tests/test_github_closure_continuation.py tests/test_github_pr_feedback.py tests/test_review_trigger_pipeline_workflow.py tests/test_closure_continuation_pipeline_workflow.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-GHA-CORE-01-2026-04-06.md`

## Scope exclusions
- Do not introduce new decision logic into GitHub workflow YAML.
- Do not change CDE, TLC, SEL core decision engines beyond adapter wiring.
- Do not alter non-GHA runtime modules unrelated to trigger/handoff/feedback hardening.
- Do not add branch mutation execution; enforce policy gating only.

## Dependencies
- Existing GHA-01 and GHA-02 pipelines must remain the authoritative trigger/route path.
- Existing RIL/CDE/TLC/SEL modules remain decision and enforcement authorities.
