# PLAN — WPG-MASTER-EXEC-04

Primary type: BUILD

## Scope executed in this change set
This execution implements the checkpoint/resume governance layer and phase-aware continuation path for the WPG pipeline (CHK-01 through CHK-05 plus WPG-51 integration), including governed schemas, examples, manifest registration, runtime logic, CLI integration, and deterministic tests.

## Ordered slices
1. Add governed contracts and examples for phase checkpoint, transition policy, resume, handoff, registry, requirement profile, and artifact-family mapping.
2. Implement phase governance runtime logic with fail-closed transition decisions.
3. Add `scripts/run_phase_transition.py` CLI for next eligible phase computation.
4. Refactor `wpg_pipeline` and `run_wpg_pipeline.py` entrypoints to consume phase registry + checkpoint/transition policy and emit checkpoint/resume artifacts.
5. Add/expand tests for contracts, phase transition CLI/runtime, and WPG phase-aware execution behavior.
6. Run focused validation, then commit and open PR artifact message.
