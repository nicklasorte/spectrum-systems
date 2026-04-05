# Plan — BATCH-FRE-03 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-FRE-03 (FRE-006/FRE-007/FRE-008)

## Objective
Implement a deterministic, fail-closed closed-loop recovery orchestrator that consumes diagnosis/repair artifacts, executes one bounded governed repair attempt, evaluates validation evidence, and emits a schema-backed recovery result artifact with deterministic retry guidance.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-FRE-03-2026-04-05.md | CREATE | Required plan-first artifact for this multi-file build slice. |
| spectrum_systems/modules/runtime/recovery_orchestrator.py | CREATE | FRE-006 bounded governed recovery orchestration implementation. |
| contracts/schemas/recovery_result_artifact.schema.json | CREATE | FRE-007 strict schema for governed recovery outputs. |
| contracts/examples/recovery_result_artifact.json | CREATE | Golden-path example for recovery result artifact contract. |
| contracts/standards-manifest.json | MODIFY | Register recovery_result_artifact and bump standards metadata. |
| tests/test_recovery_orchestrator.py | CREATE | FRE-006/FRE-008 deterministic/fail-closed orchestration tests and contract checks. |

## Contracts touched
- `contracts/schemas/recovery_result_artifact.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + registration)

## Tests that must pass after execution
1. `pytest tests/test_recovery_orchestrator.py -q`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement unconstrained autonomous recursive repair execution.
- Do not modify FRE-01 diagnosis classification behavior.
- Do not modify FRE-02 repair prompt generation template logic beyond consumption.
- Do not weaken preflight, contract enforcement, or control-gating semantics.

## Dependencies
- `docs/review-actions/PLAN-BATCH-FRE-01-2026-04-05.md` diagnosis contract/module outputs available.
- `docs/review-actions/PLAN-BATCH-FRE-02-2026-04-05.md` repair prompt contract/module outputs available.
