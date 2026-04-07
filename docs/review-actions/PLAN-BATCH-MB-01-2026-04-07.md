# Plan — BATCH-MB-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-MB-01 (MB-01) — Failure Learning + Eval Governance

## Objective
Implement a deterministic, artifact-backed failure-learning governance loop that classifies failures, emits eval candidates, gates eval adoption through CDE-owned artifacts, and generates bounded roadmap signals.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-MB-01-2026-04-07.md | CREATE | Required PLAN artifact for multi-file BUILD scope. |
| contracts/schemas/failure_class_registry.schema.json | CREATE | Define finite failure class registry contract and mapping rules. |
| contracts/examples/failure_class_registry.json | CREATE | Golden-path registry example. |
| contracts/schemas/eval_candidate_artifact.schema.json | CREATE | Governed eval-candidate contract emitted from failures. |
| contracts/examples/eval_candidate_artifact.json | CREATE | Golden-path eval-candidate example. |
| contracts/schemas/eval_adoption_decision_artifact.schema.json | CREATE | CDE-governed eval adoption gate contract. |
| contracts/examples/eval_adoption_decision_artifact.json | CREATE | Golden-path adoption decision example. |
| contracts/schemas/roadmap_signal_artifact.schema.json | CREATE | Bounded roadmap signal contract produced from failure learning records. |
| contracts/examples/roadmap_signal_artifact.json | CREATE | Golden-path roadmap signal example. |
| contracts/schemas/failure_learning_record_artifact.schema.json | MODIFY | Extend with recurrence/linkage fields and deterministic lineage requirements. |
| contracts/examples/failure_learning_record_artifact.json | MODIFY | Align example to extended failure learning schema. |
| contracts/schemas/failure_diagnosis_artifact.schema.json | MODIFY | Align failure classes to registry-controlled finite vocabulary. |
| contracts/examples/failure_diagnosis_artifact.json | MODIFY | Keep diagnosis example schema-valid after class updates. |
| contracts/schemas/failure_repair_candidate_artifact.schema.json | MODIFY | Align failure_class enum with registry classes. |
| contracts/examples/failure_repair_candidate_artifact.json | MODIFY | Keep example valid with class updates. |
| contracts/standards-manifest.json | MODIFY | Register/new versions for all touched or added contracts. |
| spectrum_systems/modules/runtime/failure_diagnosis_engine.py | MODIFY | Deterministic class registry loading, class mapping, eval-candidate generation helpers. |
| spectrum_systems/modules/runtime/closure_decision_engine.py | MODIFY | Add eval adoption decision artifact generation (approved/rejected/deferred). |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Wire artifact-only flow: failure diagnosis → learning record → eval candidate → adoption decision → roadmap signal. |
| spectrum_systems/modules/runtime/system_enforcement_layer.py | MODIFY | Add SEL fail-closed checks for registry validity, eval candidate validity, adoption-before-use, roadmap-source linkage. |
| tests/test_failure_class_registry.py | CREATE | Verify finite registry, deterministic mapping, unknown escalation semantics. |
| tests/test_eval_candidate_pipeline.py | CREATE | Verify deterministic eval candidate generation and schema validity. |
| tests/test_eval_adoption_gate.py | CREATE | Verify CDE adoption gate behavior and rationale requirements. |
| tests/test_failure_learning_artifacts.py | MODIFY | Verify recurrence/linkage behavior and historical retention. |
| tests/test_roadmap_signal_generation.py | CREATE | Verify roadmap signal generation and bounded linkage constraints. |

## Contracts touched
- failure_class_registry (new)
- eval_candidate_artifact (new)
- eval_adoption_decision_artifact (new)
- roadmap_signal_artifact (new)
- failure_learning_record_artifact (updated)
- failure_diagnosis_artifact (updated)
- failure_repair_candidate_artifact (updated)
- standards-manifest (version + registrations)

## Tests that must pass after execution
1. `pytest tests/test_failure_class_registry.py tests/test_eval_candidate_pipeline.py tests/test_eval_adoption_gate.py tests/test_failure_learning_artifacts.py tests/test_roadmap_signal_generation.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-MB-01-2026-04-07.md`

## Scope exclusions
- Do not add any new system/acronym.
- Do not add execution logic outside PQX.
- Do not add closure/adoption decision logic outside CDE.
- Do not add orchestration outside TLC.
- Do not implement automatic eval suite mutation.
- Do not modify unrelated modules, schemas, or roadmap files.

## Dependencies
- BATCH-FRE-01 (failure diagnosis/repair candidate baseline) must remain compatible.
- Existing TLC/CDE/SEL governed boundary contracts must remain fail-closed.
