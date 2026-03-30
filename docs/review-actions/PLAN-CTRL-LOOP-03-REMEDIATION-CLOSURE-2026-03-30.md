# Plan — CTRL-LOOP-03 Remediation Closure Governance — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-03

## Objective
Extend existing judgment enforcement/remediation seams with deterministic remediation lifecycle, closure, and reinstatement governance so freeze/block/warn paths remain fail-closed until closure and required reinstatement artifacts are present and replay-safe checks pass.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-03-REMEDIATION-CLOSURE-2026-03-30.md | CREATE | Required plan-first artifact for grouped multi-file BUILD slice |
| contracts/schemas/judgment_operator_remediation_record.schema.json | MODIFY | Extend status lifecycle vocabulary and deterministic transition history fields |
| contracts/schemas/judgment_remediation_closure_record.schema.json | CREATE | New governed closure artifact contract |
| contracts/schemas/judgment_progression_reinstatement_record.schema.json | CREATE | New governed reinstatement artifact contract |
| contracts/examples/judgment_operator_remediation_record.json | MODIFY | Golden-path remediation example with explicit lifecycle state model fields |
| contracts/examples/judgment_remediation_closure_record.json | CREATE | Golden-path closure artifact example |
| contracts/examples/judgment_progression_reinstatement_record.json | CREATE | Golden-path reinstatement artifact example |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump standards manifest version |
| spectrum_systems/modules/runtime/judgment_enforcement.py | MODIFY | Add lifecycle transitions, replay-safe closure checks, closure/reinstatement builders, and fail-closed progression gating |
| tests/test_judgment_enforcement.py | MODIFY | Integration coverage for remediation->closure->reinstatement progression behavior and determinism |
| tests/test_contracts.py | MODIFY | Validate new contract examples |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document remediation lifecycle, closure checks, reinstatement gating, and resume semantics |
| docs/roadmaps/system_roadmap.md | MODIFY | Record authoritative roadmap status/update for remediation closure governance bundle |
| docs/roadmap/system_roadmap.md | MODIFY | Keep compatibility roadmap mirror in lockstep |

## Contracts touched
- judgment_operator_remediation_record (schema extension)
- judgment_remediation_closure_record (new)
- judgment_progression_reinstatement_record (new)
- standards-manifest version bump and contract registration

## Tests that must pass after execution
1. `pytest tests/test_judgment_enforcement.py tests/test_control_loop.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign the control loop architecture.
- Do not create a parallel remediation/control plane.
- Do not refactor unrelated runtime or queue modules.

## Dependencies
- CTRL-LOOP-02 enforcement wiring slice must be present and passing.
