# Plan — CON-032 Fix: Reconcile Preflight BLOCK — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-032-FIX — reconcile preflight BLOCK and harden gap→PQX propagation

## Objective
Resolve the exact current preflight BLOCK by repairing only propagation/coverage seams causing false blocking signals, while preserving fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-032-FIX-RECONCILE-PREFLIGHT-BLOCK-2026-04-02.md | CREATE | Required PLAN artifact before multi-file repair. |
| PLANS.md | MODIFY | Register active CON-032-FIX plan. |
| tests/test_pqx_slice_runner.py | MODIFY | Align preflight fixture artifact with current contract fields to remove false producer failure. |
| tests/test_control_surface_gap_extractor.py | MODIFY | Add deterministic CLI path coverage so changed-path required-surface mapping finds evaluation target for `scripts/run_control_surface_gap_extraction.py`. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_contract_preflight.py tests/test_control_surface_gap_extractor.py tests/test_control_surface_gap_to_pqx.py`
2. `pytest -q tests/test_pqx_slice_runner.py tests/test_contracts.py`
3. `python scripts/run_contract_preflight.py --base-ref "80409a2ba7c14aee6b2de79e308a0f7384bed5e8" --head-ref "86df5c0fce6db7f3093358ca73e0bec651c49f2d" --output-dir outputs/contract_preflight`
4. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-CON-032-FIX-RECONCILE-PREFLIGHT-BLOCK-2026-04-02.md tests/test_pqx_slice_runner.py tests/test_control_surface_gap_extractor.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify runtime extraction/adapter logic unless required by the exact current BLOCK.
- Do not relax preflight policy gates.
- Do not redesign CON-032 contracts or add new artifact types.

## Dependencies
- CON-032 implementation commit present on branch.
- Source-of-truth preflight artifacts under `outputs/contract_preflight/` available for diagnosis.
