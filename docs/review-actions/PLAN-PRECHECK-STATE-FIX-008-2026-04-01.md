# Plan — PRECHECK-STATE-FIX-008 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
PRECHECK-STATE-FIX-008

## Objective
Repair the contract preflight → PQX integration crash by fixing the exact contract-impact seam so preflight emits governed output and no longer blocks this branch due analyzer/schema mismatch.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PRECHECK-STATE-FIX-008-2026-04-01.md | CREATE | Required PLAN for multi-file repair. |
| scripts/run_contract_preflight.py | MODIFY | Repair changed-contract intake so contract impact analysis only receives compatible schema paths and still reports governed definitions. |
| tests/test_contract_preflight.py | MODIFY | Add targeted regression tests for mixed schema/governed-definition changed-path inputs and no-crash preflight emission. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Break runtime/governance import cycle triggered during preflight targeted consumer test collection. |
| tests/test_pqx_slice_runner.py | MODIFY | Add regression test proving runtime module import no longer raises done-certification circular import errors. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_contract_preflight.py --base-ref "4d3e38ba5f59ee3f6a6d89c73c911663e57fc383" --head-ref "b756c06a026443dbac95e4a18019839894567714" --output-dir outputs/contract_preflight`
2. `pytest tests/test_contract_preflight.py`
3. `pytest tests/test_pqx_slice_runner.py tests/test_contract_preflight.py tests/test_contracts.py`

## Scope exclusions
- Do not weaken preflight exit semantics (status failed still returns exit code 2).
- Do not modify PQX BLOCK/WARN/FREEZE/ALLOW enforcement behavior.
- Do not rollback schemas/artifacts introduced in PRECHECK-STATE-007.

## Dependencies
- PRECHECK-STATE-007 contract preflight artifact and PQX consumption remain authoritative inputs.
