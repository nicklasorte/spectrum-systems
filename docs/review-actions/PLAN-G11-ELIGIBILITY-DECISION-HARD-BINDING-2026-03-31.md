# Plan — G11 Eligibility → Decision Hard Binding — 2026-03-31

## Prompt type
PLAN

## Roadmap item
G11 — Eligibility to decision hard binding (control-layer hardening slice)

## Objective
Enforce fail-closed control-layer coupling so next-step decision and cycle progression can only proceed using a valid roadmap eligibility artifact and an eligibility-authorized selected step.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-G11-ELIGIBILITY-DECISION-HARD-BINDING-2026-03-31.md | CREATE | Required PLAN artifact before multi-file/schema BUILD work. |
| PLANS.md | MODIFY | Register newly created active plan in repository plan index. |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY | Require eligibility artifact input, enforce eligible-only selected step, and emit eligibility provenance in decision artifact. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Enforce eligibility artifact precondition, persist eligibility/selected-step linkage, and block progression on invalid eligibility decision outcomes. |
| scripts/run_next_step_decision.py | MODIFY | Wire new required eligibility input argument for decision CLI path. |
| contracts/schemas/next_step_decision_artifact.schema.json | MODIFY | Add eligibility provenance + selected step fields as required contract properties. |
| contracts/examples/next_step_decision_artifact.json | MODIFY | Update golden-path examples with eligibility provenance and selected-step fields. |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add eligibility and selected-step linkage fields and conditional requirements when decision artifact is present. |
| contracts/examples/cycle_manifest.json | MODIFY | Add eligibility path and selected-step linkage example fields. |
| contracts/standards-manifest.json | MODIFY | Bump schema versions/manifest metadata for changed contracts. |
| tests/test_next_step_decision.py | MODIFY | Add eligibility hard-gate tests (missing artifact, empty eligibility, non-eligible selection, provenance). |
| tests/test_next_step_decision_policy.py | MODIFY | Update decision invocations for new required eligibility input path. |
| tests/test_cycle_runner.py | MODIFY | Add cycle-runner eligibility gate and selected-step persistence tests. |

## Contracts touched
- `contracts/schemas/next_step_decision_artifact.schema.json` (version bump + additive required fields)
- `contracts/schemas/cycle_manifest.schema.json` (version bump + additive/conditional required fields)
- `contracts/standards-manifest.json` (contract version registry updates)

## Tests that must pass after execution
1. `pytest tests/test_next_step_decision.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not modify PQX execution layer runtime adapters.
- Do not redesign next-step policy mapping semantics beyond eligibility gating and provenance.
- Do not alter roadmap planning contracts or authoring flows.

## Dependencies
- Existing roadmap eligibility artifact contract (`roadmap_eligibility_artifact`) remains authoritative and consumable.
- Existing next-step decision policy artifact remains authoritative for state-to-action mapping.
