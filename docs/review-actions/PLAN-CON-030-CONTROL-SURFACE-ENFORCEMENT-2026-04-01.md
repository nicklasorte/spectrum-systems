# Plan — CON-030 Control Surface Manifest Enforcement — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CON-030 — Control Surface Manifest Enforcement

## Objective
Make the CON-029 control surface manifest an active fail-closed enforcement artifact and wire deterministic blocking semantics into contract preflight.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-030-CONTROL-SURFACE-ENFORCEMENT-2026-04-01.md | CREATE | Required PLAN artifact for this multi-file contract/module enforcement slice. |
| PLANS.md | MODIFY | Register active CON-030 plan in the plan index. |
| contracts/schemas/control_surface_enforcement_result.schema.json | CREATE | Publish governed contract for machine-readable enforcement output. |
| contracts/examples/control_surface_enforcement_result.json | CREATE | Golden-path example for new enforcement contract. |
| contracts/standards-manifest.json | MODIFY | Pin new enforcement-result artifact contract in canonical manifest. |
| spectrum_systems/modules/runtime/control_surface_enforcement.py | CREATE | Implement pure deterministic fail-closed enforcement evaluator. |
| scripts/run_control_surface_enforcement.py | CREATE | Provide thin CLI wrapper with non-zero exit on block/malformed input. |
| scripts/run_contract_preflight.py | MODIFY | Wire enforcement into contract preflight seam with machine-readable block reasons. |
| tests/test_control_surface_enforcement.py | CREATE | Focused regression coverage for module/CLI fail-closed behavior. |
| tests/test_contract_preflight.py | MODIFY | Validate preflight machine-readable block behavior when enforcement fails. |

## Contracts touched
- `contracts/schemas/control_surface_enforcement_result.schema.json` (new, v1.0.0)
- `contracts/standards-manifest.json` (add `control_surface_enforcement_result` pin)

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_manifest.py tests/test_control_surface_enforcement.py tests/test_contract_preflight.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py tests/test_evaluation_control.py tests/test_sequence_transition_policy.py tests/test_done_certification.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/build_control_surface_manifest.py --output-dir outputs/control_surface_manifest`
5. `python scripts/run_control_surface_enforcement.py --manifest outputs/control_surface_manifest/control_surface_manifest.json --output-dir outputs/control_surface_enforcement`
6. `python scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/control_surface_enforcement.py --changed-path scripts/run_control_surface_enforcement.py --changed-path contracts/schemas/control_surface_enforcement_result.schema.json --changed-path contracts/examples/control_surface_enforcement_result.json --changed-path tests/test_control_surface_enforcement.py --changed-path contracts/standards-manifest.json`
7. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-CON-030-CONTROL-SURFACE-ENFORCEMENT-2026-04-01.md contracts/schemas/control_surface_enforcement_result.schema.json contracts/examples/control_surface_enforcement_result.json contracts/standards-manifest.json spectrum_systems/modules/runtime/control_surface_enforcement.py scripts/run_control_surface_enforcement.py tests/test_control_surface_enforcement.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign control-surface catalog semantics from CON-029.
- Do not add auto-discovery heuristics for required surfaces.
- Do not broaden enforcement into unrelated governance seams beyond narrow preflight wiring.
- Do not weaken existing fail-closed logic or downgrade blocking conditions.

## Dependencies
- CON-029 control surface manifest contract/module/CLI baseline must be present.
