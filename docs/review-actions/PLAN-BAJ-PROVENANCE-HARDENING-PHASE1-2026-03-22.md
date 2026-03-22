# Plan — BAJ Provenance Hardening Phase 1 — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAJ Provenance Hardening — Phase 1 (narrow spine fix)

## Objective
Harden the primary runtime provenance spine by selecting one authoritative provenance schema for the main path and enforcing explicit, validated policy + trace + runtime provenance fields at shared emitter and study-runner emission points.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAJ-PROVENANCE-HARDENING-PHASE1-2026-03-22.md | CREATE | Required PLAN artifact for multi-file BUILD scope. |
| PLANS.md | MODIFY | Register this new active plan per repository planning lifecycle. |
| schemas/provenance-schema.json | MODIFY | Designate/align authoritative schema for primary runtime provenance path and add required trace linkage fields. |
| shared/artifact_models/artifact_metadata.schema.json | MODIFY | Require policy identity in shared artifact metadata contract. |
| shared/adapters/artifact_emitter.py | MODIFY | Require/validate `policy_id`; emit provenance record; validate against authoritative provenance schema. |
| spectrum_systems/study_runner/artifact_writer.py | MODIFY | Require validated trace/runtime provenance context and fail-closed behavior before writes. |
| spectrum_systems/study_runner/run_study.py | MODIFY | Provide explicit provenance runtime context into `write_outputs()`. |
| tests/test_provenance_schema.py | MODIFY | Add bounded schema-authority and required trace-linkage assertions. |
| tests/test_lifecycle_enforcer.py | MODIFY | Update shared emitter tests for required `policy_id` and malformed-policy failures. |
| tests/test_artifact_packaging_and_study_state.py | MODIFY | Add focused study-runner provenance fail-closed and runtime-derived field tests. |
| docs/reviews/BAJ_provenance_hardening_fix_report.md | CREATE | Mandatory implementation report with finding mapping, bounded scope, tests, and deferred gaps. |

## Contracts touched
- `schemas/provenance-schema.json` (authoritative provenance schema for this patch path)
- `shared/artifact_models/artifact_metadata.schema.json` (shared metadata contract, additive `policy_id` requirement)

## Tests that must pass after execution
1. `pytest -q tests/test_provenance_schema.py`
2. `pytest -q tests/test_artifact_packaging_and_study_state.py`
3. `pytest -q tests/test_artifact_envelope.py`
4. `pytest -q tests/test_trace_engine.py`
5. `pytest -q tests/test_policy_registry.py`
6. `pytest -q tests/test_lifecycle_enforcer.py`
7. `pytest -q`

## Scope exclusions
- Do not perform full repository-wide provenance schema consolidation.
- Do not redesign strategic-knowledge provenance model in this phase unless required for non-breaking bounded compatibility (defer by default).
- Do not change unrelated artifact systems, lifecycle architecture, or trace engine internals.
- Do not add inferred/default placeholder provenance values for missing required fields.

## Dependencies
- Existing trace validation API in `spectrum_systems/modules/runtime/trace_engine.py` must remain available for fail-closed gating.
- Existing policy registry validation path in `spectrum_systems/modules/runtime/policy_registry.py` must remain available for policy enforcement.
