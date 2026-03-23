# Plan — BAJ Provenance Hardening Phase 2 — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Prompt BAJ — Provenance hardening trust-boundary remediation

## Objective
Establish one canonical provenance build/validation path and route high-risk runtime, replay, drift, enforcement, and strategic-knowledge emitters through fail-closed provenance enforcement.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAJ-PROVENANCE-HARDENING-PHASE2-2026-03-23.md | CREATE | Required PLAN artifact for multi-file trust-boundary build. |
| spectrum_systems/modules/runtime/provenance.py | CREATE | Canonical provenance builder/validator/revalidation utility module. |
| spectrum_systems/modules/runtime/enforcement_engine.py | MODIFY | Route enforcement emitter through canonical provenance path. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Route replay emitter/attachment mutation path through canonical provenance and fail-closed trace requirements. |
| spectrum_systems/modules/runtime/drift_detection_engine.py | MODIFY | Route drift attachment/output through canonical provenance path. |
| spectrum_systems/modules/strategic_knowledge/validator.py | MODIFY | Remove synthetic trace/span fallback and enforce fail-closed context requirements. |
| spectrum_systems/modules/runtime/__init__.py | MODIFY | Export canonical provenance APIs. |
| contracts/schemas/enforcement_result.schema.json | MODIFY | Strengthen provenance requirements for enforcement artifacts. |
| contracts/schemas/replay_result.schema.json | MODIFY | Strengthen provenance requirements for replay artifacts and nested drift attachment provenance. |
| contracts/schemas/drift_result.schema.json | MODIFY | Strengthen provenance requirements for drift result artifacts. |
| contracts/schemas/strategic_knowledge_validation_decision.schema.json | MODIFY | Add canonical provenance requirement for strategic-knowledge decision artifacts. |
| contracts/examples/enforcement_result.json | MODIFY | Keep contract example aligned with strengthened provenance shape. |
| contracts/examples/replay_result.json | MODIFY | Keep contract example aligned with strengthened provenance shape. |
| contracts/examples/drift_result.json | MODIFY | Keep contract example aligned with strengthened provenance shape. |
| contracts/standards-manifest.json | MODIFY | Version bump and schema version pin updates for changed contracts. |
| tests/test_replay_engine.py | MODIFY | Add/adjust canonical provenance and fail-closed trace-context coverage. |
| tests/test_drift_detection_engine.py | MODIFY | Ensure canonical provenance requirements are enforced for drift output. |
| tests/test_strategic_knowledge_validator.py | MODIFY | Verify missing trace context fails closed and synthetic fallback is removed. |
| tests/test_strategic_knowledge_validation_decision_schema.py | MODIFY | Ensure decision schema enforces canonical provenance presence/shape. |
| tests/test_provenance_canonicalization.py | CREATE | Required targeted trust tests for canonical builder usage, parity, and mutation revalidation. |

## Contracts touched
- enforcement_result.schema.json
- replay_result.schema.json
- drift_result.schema.json
- strategic_knowledge_validation_decision.schema.json
- contracts/standards-manifest.json (version bumps)

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py tests/test_drift_detection_engine.py tests/test_strategic_knowledge_validator.py tests/test_strategic_knowledge_validation_decision_schema.py tests/test_provenance_canonicalization.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not broaden into CI guard/automation work.
- Do not migrate lower-risk emitters outside runtime/replay/drift/enforcement/SK trust-boundary surfaces.
- Do not refactor unrelated modules or rename artifact families.
- Do not weaken any schema requirement to allow partial provenance.

## Dependencies
- Existing BAJ Phase 1 provenance hardening baseline remains in place.
