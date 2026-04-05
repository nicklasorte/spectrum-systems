# Plan — BATCH-FRE-04 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-FRE-04 (FRE-REV-01, FRE-REV-02, FRE-REV-03)

## Objective
Harden FRE recovery orchestration so retry exhaustion always emits a valid terminal artifact, every legal FRE-01 root cause deterministically maps through FRE-02, and FRE-03 execution attempts require explicit governance gate evidence.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-FRE-04-2026-04-05.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| spectrum_systems/modules/runtime/recovery_orchestrator.py | MODIFY | Implement retry-exhaustion terminal artifact emission and governance evidence requirements at execution handoff. |
| spectrum_systems/modules/runtime/repair_prompt_generator.py | MODIFY | Add deterministic template/fallback coverage for all legal FRE-01 primary root causes. |
| contracts/schemas/repair_prompt_artifact.schema.json | MODIFY | Extend allowed deterministic template IDs for newly covered root-cause classes. |
| contracts/examples/repair_prompt_artifact.json | MODIFY | Keep canonical example aligned with schema/contract version changes if needed. |
| contracts/standards-manifest.json | MODIFY | Version-pin contract updates for any schema version changes. |
| tests/test_recovery_orchestrator.py | MODIFY | Add retry-exhaustion and governance-evidence fail-closed/allow tests. |
| tests/test_repair_prompt_generator.py | MODIFY | Add full root-cause matrix coverage and deterministic fallback assertions. |

## Contracts touched
- `contracts/schemas/repair_prompt_artifact.schema.json` (expected additive enum extension and version bump).

## Tests that must pass after execution
1. `pytest tests/test_repair_prompt_generator.py tests/test_recovery_orchestrator.py -q`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign FRE architecture or collapse FRE-01/FRE-02/FRE-03 responsibilities.
- Do not weaken schema required fields or loosen fail-closed behavior.
- Do not modify unrelated modules, queue runtime, or roadmap execution wiring.

## Dependencies
- Existing FRE baseline from BATCH-FRE-01, BATCH-FRE-02, and BATCH-FRE-03 must remain intact.
