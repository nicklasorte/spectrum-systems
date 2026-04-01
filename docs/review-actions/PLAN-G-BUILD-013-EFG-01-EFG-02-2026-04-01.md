# Plan — G-BUILD-013 EFG-01 + EFG-02 Gate-Proof Hardening — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CL hardening overlay — Build Step 1 (EFG-01 + EFG-02)

## Objective
Encode control-loop hard-gate pass conditions as required certification evidence and enforce fail-closed transition blocking when severity-qualified failure binding to eval/policy updates is missing.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-G-BUILD-013-EFG-01-EFG-02-2026-04-01.md | CREATE | Declare constrained BUILD scope before multi-file contract/runtime/test changes. |
| contracts/schemas/control_loop_certification_pack.schema.json | MODIFY | Add first-class required hard-gate evidence/check surfaces for EFG-01. |
| contracts/examples/control_loop_certification_pack.json | MODIFY | Keep golden-path contract example aligned to strengthened schema. |
| contracts/standards-manifest.json | MODIFY | Publish schema version bump for strengthened certification contract. |
| scripts/run_control_loop_certification.py | MODIFY | Enforce fail-closed validation of strengthened hard-gate evidence and encode output fields. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Fail closed progression when severity-qualified failure-binding enforcement evidence is missing (EFG-02). |
| tests/test_control_loop_certification.py | MODIFY | Add targeted tests for strengthened hard-gate evidence and fail-closed certification behavior. |
| tests/test_sequence_transition_policy.py | MODIFY | Add targeted tests for non-bypassable failure-binding transition enforcement. |

## Contracts touched
- `control_loop_certification_pack` schema version bump and example update.
- `contracts/standards-manifest.json` publication metadata update for the same contract.

## Tests that must pass after execution
1. `pytest tests/test_control_loop_certification.py tests/test_sequence_transition_policy.py -q`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
3. `python scripts/run_contract_enforcement.py`
4. `PLAN_FILES="docs/review-actions/PLAN-G-BUILD-013-EFG-01-EFG-02-2026-04-01.md contracts/schemas/control_loop_certification_pack.schema.json contracts/examples/control_loop_certification_pack.json contracts/standards-manifest.json scripts/run_control_loop_certification.py spectrum_systems/orchestration/sequence_transition_policy.py tests/test_control_loop_certification.py tests/test_sequence_transition_policy.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not alter roadmap authority files or rewrite roadmap ordering.
- Do not introduce new modules or abstraction layers beyond existing certification/transition seams.
- Do not weaken any fail-closed checks or admission gate criteria.

## Dependencies
- Active authority stack from `docs/architecture/strategy-control.md` and `docs/roadmaps/system_roadmap.md` remains in force.
- Existing CL-01/CL-03 recurrence/failure binding surfaces in runtime modules remain authoritative inputs.
