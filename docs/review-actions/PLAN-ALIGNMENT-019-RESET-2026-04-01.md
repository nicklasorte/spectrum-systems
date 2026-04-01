# Plan — ALIGNMENT-019-RESET — 2026-04-01

## Prompt type
PLAN

## Roadmap item
ALIGNMENT-019-RESET — Foundation Alignment Reset (Trust Spine Closure, Preflight-First)

## Objective
Harden the single governed trust spine so promotion/certification cannot bypass hard-gate falsification or failure-binding proof, with deterministic preflight-first validation and trace-stable evidence.

## Declared files
List every file that will be created, modified, or deleted. No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ALIGNMENT-019-RESET-2026-04-01.md | CREATE | Required plan-first artifact for this multi-file hardening bundle |
| PLANS.md | MODIFY | Register new active plan per repository plan governance |
| contracts/schemas/control_loop_certification_pack.schema.json | MODIFY | Encode certification-side hard-gate falsification requirement as governed machine-checkable fields |
| contracts/examples/control_loop_certification_pack.json | MODIFY | Keep golden-path certification example aligned with updated contract fields |
| contracts/standards-manifest.json | MODIFY | Version-bump and document updated certification pack contract semantics |
| scripts/run_control_loop_certification.py | MODIFY | Ensure producer emits required hard-gate falsification evidence fields deterministically |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Ensure promotion consumer can deterministically consume falsification evidence via certification pack fallback path |
| tests/test_control_loop_certification.py | MODIFY | Cover producer + gate-proof validation for new mandatory falsification evidence fields |
| tests/test_sequence_transition_policy.py | MODIFY | Cover transition-policy consumption fallback to certification pack falsification evidence |
| tests/test_cycle_runner.py | MODIFY | Align cycle-runner promotion tests with certification-pack falsification fallback consumption semantics |

## Contracts touched
- `contracts/schemas/control_loop_certification_pack.schema.json` (schema version increment expected)
- `contracts/standards-manifest.json` entry for `control_loop_certification_pack`
- `contracts/examples/control_loop_certification_pack.json`

## Tests that must pass after execution
1. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-ALIGNMENT-019-RESET-2026-04-01.md`
2. `pytest tests/test_control_loop_certification.py tests/test_sequence_transition_policy.py tests/test_cycle_runner.py -q`
3. `pytest tests/test_contract_preflight.py tests/test_contracts.py tests/test_contract_enforcement.py -q`
4. `pytest tests/test_done_certification.py tests/test_execution_change_impact_analysis.py -q`
5. `python scripts/run_contract_enforcement.py`
6. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight`

## Scope exclusions
- Do not add new modules or parallel orchestration/control subsystems.
- Do not weaken existing hard-gate falsification, failure-binding, or recurrence-prevention semantics.
- Do not broaden roadmap capability or agent expansion surfaces.
- Do not modify unrelated contracts or artifacts outside declared trust-spine seams.

## Dependencies
- Existing trust-spine modules and contracts already present in repository state.
- Preflight will be checked early (immediately after implementation) before broader pytest surfaces.
