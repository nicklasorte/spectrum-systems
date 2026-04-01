# Plan — CON-030 Preflight BLOCK Reconciliation — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CON-030 — Control Surface Manifest Enforcement (preflight reconciliation)

## Objective
Remove the false-positive preflight BLOCK by scoping control-surface enforcement invocation to manifest-governance change paths only, while preserving fail-closed enforcement behavior when the manifest seam itself changes.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-030-PREFLIGHT-FIX-2026-04-01.md | CREATE | Required plan-first artifact for this multi-file fix slice. |
| PLANS.md | MODIFY | Register active preflight-fix plan. |
| scripts/run_contract_preflight.py | MODIFY | Narrow enforcement trigger to manifest seam paths; keep fail-closed semantics. |
| tests/test_contract_preflight.py | MODIFY | Update/add targeted regression coverage for narrowed trigger behavior. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_contract_preflight.py --base-ref "c17a3a3066b0349bc5ace0f6972b2a270fd0c35a" --head-ref "3fa30114f9c13205a956c6b80a30635ea947cba9" --output-dir outputs/contract_preflight`
2. `pytest -q tests/test_contract_preflight.py tests/test_control_surface_manifest.py tests/test_control_surface_enforcement.py tests/test_contracts.py tests/test_contract_enforcement.py tests/test_done_certification.py`
3. `python scripts/run_contract_enforcement.py`
4. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-CON-030-PREFLIGHT-FIX-2026-04-01.md scripts/run_contract_preflight.py tests/test_contract_preflight.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify control surface enforcement schema/example/module semantics.
- Do not alter done certification wiring.
- Do not weaken BLOCK logic when manifest seam is in scope.

## Dependencies
- CON-030 implementation commit must be present.
