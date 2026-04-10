# Plan — BATCH-AUT-REG-02 — 2026-04-10

## Prompt type
PLAN

## Roadmap item
BATCH-AUT-REG-02

## Objective
Upgrade the canonical slice registry into an execution-ready contract by adding enforceable execution fields, fail-closed validation, and PQX compatibility checks without altering slice ownership or structure.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/roadmap/slice_registry.json | MODIFY | Add required execution fields (`execution_type`, `commands`, `success_criteria`) for every slice with deterministic executable commands. |
| spectrum_systems/modules/runtime/roadmap_slice_registry.py | MODIFY | Enforce new required execution fields and fail-closed deterministic command validation. |
| tests/test_roadmap_slice_registry.py | MODIFY | Add surgical fail-closed tests for missing/empty execution fields and valid pass case. |
| tests/test_execution_hierarchy.py | MODIFY | Add thin compatibility assertion for registry execution-readiness consumption boundary. |
| tests/test_prompt_queue_execution_loop.py | MODIFY | Add thin compatibility check that registry-backed execution metadata can be consumed independent of prompt prose. |
| docs/reviews/RVW-BATCH-AUT-REG-02.md | CREATE | Mandatory review artifact with execution-readiness verdict and risk answers. |
| docs/reviews/BATCH-AUT-REG-02-DELIVERY-REPORT.md | CREATE | Delivery report covering fields added, validations, tests, and remaining gaps. |

## Contracts touched
- `contracts/roadmap/slice_registry.json` (artifact contract surface extended additively; no breaking field removals)

## Tests that must pass after execution
1. `pytest tests/test_roadmap_slice_registry.py -q`
2. `pytest tests/test_execution_hierarchy.py tests/test_prompt_queue_execution_loop.py -q`
3. `python scripts/run_contract_preflight.py --output-dir outputs/preflight`

## Scope exclusions
- Do not modify PQX execution runtime behavior beyond read/compatibility checks.
- Do not add or remove slices, systems, or ownership roles.
- Do not weaken existing fail-closed validation constraints.
- Do not perform unrelated refactors outside the declared files.

## Dependencies
- Canonical alignment with `README.md` and `docs/architecture/system_registry.md` remains mandatory.
