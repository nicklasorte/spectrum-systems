# Plan — RAX-HARDEN-CRITICAL-01 — 2026-04-11

## Prompt type
BUILD

## Scope
Harden the existing roadmap realization runner to fail closed against six known critical red-team attack classes, without broadening roadmap realization scope beyond RF-02/RF-03.

## Files expected to change
| Path | Action | Purpose |
| --- | --- | --- |
| `scripts/roadmap_realization_runner.py` | MODIFY | Add strict contract checks, dependency/ownership/test integrity gates, stronger forbidden-pattern detection, and fail-closed result semantics. |
| `spectrum_systems/modules/runtime/roadmap_realization_runtime.py` | MODIFY | Tighten dependency/status transition rules with runtime-authoritative state advancement semantics. |
| `tests/test_roadmap_realization_runner.py` | MODIFY | Add regression tests for all six critical attack classes and fail-closed semantics. |

## Execution steps
1. Add explicit contract validation for required non-empty runtime fields and prevent realization attempt on validation failure.
2. Enforce runtime-authoritative status transitions that ignore caller-forged `realization_status` values.
3. Enforce dependency existence/order/status checks with explicit failure reasons.
4. Enforce owner-to-module and owner-to-test prefix policy from expansion policy before execution.
5. Replace naive forbidden-pattern scanning with stronger static pattern heuristics scoped to target modules and runner/runtime helpers.
6. Enforce constrained behavioral test command policy and reject weak/non-behavioral commands.
7. Guarantee fail-closed result semantics (`overall_status`, `passed_steps`, `status_updates`) across all critical validation categories.
8. Add targeted regression tests for dependency bypass, forbidden-pattern evasion, fake test success, status forging, ownership boundary attack, and malformed contracts.

## Validation commands
1. `pytest tests/test_roadmap_realization_runner.py -q`
2. `pytest tests/test_roadmap_expansion_contracts.py -q`
