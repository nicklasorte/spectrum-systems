# Plan — BATCH-GHA-08 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GHA-08 (GHA-008)

## Objective
Add a bounded pre-PR repair-loop behavior across existing systems (RIL/FRE/CDE/TLC/PQX/SEL) with strict terminal-state PR gating and artifactized failure learning.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-08-2026-04-07.md | CREATE | Required PLAN artifact for multi-file BUILD scope. |
| contracts/schemas/failure_repair_candidate_artifact.schema.json | CREATE | Add strict contract for FRE bounded repair candidate output. |
| contracts/examples/failure_repair_candidate_artifact.json | CREATE | Golden-path example for failure_repair_candidate_artifact. |
| contracts/schemas/repair_attempt_record_artifact.schema.json | CREATE | Add strict contract for TLC/PQX attempt records. |
| contracts/examples/repair_attempt_record_artifact.json | CREATE | Golden-path example for repair attempt records. |
| contracts/schemas/failure_learning_record_artifact.schema.json | CREATE | Add strict contract for recurrence-based learning capture. |
| contracts/examples/failure_learning_record_artifact.json | CREATE | Golden-path example for failure learning records. |
| contracts/schemas/closure_decision_artifact.schema.json | MODIFY | Permit continue_repair_bounded and bounded_repair CDE outputs. |
| contracts/schemas/system_enforcement_result_artifact.schema.json | MODIFY | Permit repair-specific SEL violation codes in governed outputs. |
| contracts/standards-manifest.json | MODIFY | Register new artifacts and bump standards version. |
| spectrum_systems/modules/runtime/failure_diagnosis_engine.py | MODIFY | Extend FRE with bounded repair-candidate derivation. |
| spectrum_systems/modules/runtime/closure_decision_engine.py | MODIFY | Add continue_repair_bounded deterministic CDE decision path. |
| spectrum_systems/modules/runtime/system_enforcement_layer.py | MODIFY | Enforce repair-loop scope, budget, and artifact boundary rules. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Orchestrate bounded pre-PR repair loop and learning artifact emission. |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Gate PR promotion on ready_for_merge only. |
| .github/workflows/closure_continuation_pipeline.yml | MODIFY | Reflect ready_for_merge-only promotion policy visibility. |
| docs/architecture/system_registry.md | MODIFY | Document ownership mapping for repair-loop behavior. |
| tests/test_pre_pr_repair_loop.py | CREATE | Focused tests for bounded pre-PR repair loop behavior. |
| tests/test_failure_learning_artifacts.py | CREATE | Tests for failure learning record creation and recurrence increments. |
| tests/test_closure_decision_engine.py | MODIFY | Add CDE tests for continue_repair_bounded behavior. |
| tests/test_top_level_conductor.py | MODIFY | Add TLC bounded-loop and terminal-state gating tests. |
| tests/test_closure_continuation_pipeline_workflow.py | MODIFY | Assert workflow read-only behavior outside ready_for_merge terminal state. |
| tests/test_system_handoff_integrity.py | MODIFY | Extend handoff assertions for repair-loop artifacts. |

## Contracts touched
- contracts/schemas/failure_repair_candidate_artifact.schema.json (new 1.0.0)
- contracts/schemas/repair_attempt_record_artifact.schema.json (new 1.0.0)
- contracts/schemas/failure_learning_record_artifact.schema.json (new 1.0.0)
- contracts/schemas/closure_decision_artifact.schema.json (enum extension)
- contracts/schemas/system_enforcement_result_artifact.schema.json (violation code extension)
- contracts/standards-manifest.json (version bump + registrations)

## Tests that must pass after execution
1. `pytest tests/test_pre_pr_repair_loop.py tests/test_failure_learning_artifacts.py`
2. `pytest tests/test_top_level_conductor.py tests/test_closure_decision_engine.py tests/test_system_handoff_integrity.py tests/test_closure_continuation_pipeline_workflow.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-GHA-08-2026-04-07.md`

## Scope exclusions
- Do not introduce a new 3-letter subsystem.
- Do not move decision logic into GitHub workflow YAML.
- Do not add non-deterministic or open-ended self-editing behavior.
- Do not auto-modify eval suites or policies from learning outputs in this slice.

## Dependencies
- Existing FRE, CDE, TLC, PQX, SEL implementation surfaces remain authoritative.
- Existing closure-continuation workflow and artifact contracts remain baseline integration surfaces.
