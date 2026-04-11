# Plan — RQ-MASTER-36-01-PHASE-3-MERGED — 2026-04-11

## Prompt type
BUILD

## Roadmap item
RQ-MASTER-36-01-PHASE-3-MERGED

## Objective
Harden guidance and control so next-action selection, degraded-data behavior, error-budget consumption, recurrence prevention, and judgment usage are deterministic, fail-closed, and traceable.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Enforce deterministic hard-gate/blocked-run priority, missing-data degradation, and stronger guidance provenance. |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Strengthen explicit error-budget-to-control and judgment consumption checks where needed. |
| tests/test_system_cycle_operator.py | MODIFY | Add deterministic coverage for hard-gate priority and degraded guidance under missing artifacts. |
| tests/test_control_loop.py | MODIFY | Add/adjust checks for control enforcement outcomes and consumption invariants. |
| docs/reviews/RVW-RQ-MASTER-36-01-PHASE-3-MERGED.md | CREATE | Required phase review with verdict and mandated questions. |
| docs/reviews/RQ-MASTER-36-01-PHASE-3-MERGED-DELIVERY-REPORT.md | CREATE | Required delivery report summarizing implementation and remaining gaps. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_control_loop.py`
3. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not introduce any new authority-owning system.
- Do not move decision authority to dashboard surfaces.
- Do not perform unrelated refactors outside guidance/control hardening scope.

## Dependencies
- Existing control-loop/judgment baseline in `spectrum_systems/modules/runtime/control_loop.py` must remain schema-valid and deterministic.
