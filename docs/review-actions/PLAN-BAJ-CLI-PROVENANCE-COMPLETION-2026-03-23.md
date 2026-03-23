# Plan — BAJ CLI Provenance Completion — 2026-03-23

## Prompt type
PLAN

## Roadmap item
BAJ migration completion — strategic-knowledge CLI provenance hardening alignment

## Objective
Align strategic-knowledge CLI and tests with fail-closed explicit trace-context requirements while keeping machine-readable output deterministic.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| scripts/validate_strategic_knowledge_artifact.py | MODIFY | Require explicit trace context in CLI inputs and emit deterministic JSON output across success/failure paths. |
| spectrum_systems/modules/strategic_knowledge/validator.py | MODIFY | Remove synthetic trace/span fallback and enforce explicit trace context for governed decision generation. |
| tests/test_validate_strategic_knowledge_artifact_cli.py | MODIFY | Migrate CLI invocations to explicit trace context and assert fail-closed + deterministic machine-readable output. |
| tests/test_strategic_knowledge_validator.py | MODIFY | Align validator unit tests to explicit trace-context requirements and add fail-closed coverage. |
| PLANS.md | MODIFY | Register this plan in Active plans table. |
| docs/review-actions/PLAN-BAJ-CLI-PROVENANCE-COMPLETION-2026-03-23.md | CREATE | Record required PLAN artifact for this multi-file BUILD change. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_validate_strategic_knowledge_artifact_cli.py`
2. `pytest tests/test_strategic_knowledge_validator.py`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not weaken strategic-knowledge provenance requirements.
- Do not reintroduce synthetic trace/span fallback generation.
- Do not modify unrelated modules, contracts, or schemas.

## Dependencies
- docs/review-actions/PLAN-BAJ-PROVENANCE-HARDENING-PHASE1-2026-03-22 must remain intact as prior hardening baseline.
