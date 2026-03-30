# Plan — Autonomous Execution Loop Closed-Loop Wiring — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 (closed-loop extension)

## Objective
Extend the existing autonomous execution foundation to live-wire PQX and GOV-10 handoffs with deterministic write-back and fail-closed integration coverage from `execution_ready` to `certified_done`.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-CLOSED-2026-03-30.md | CREATE | Required multi-file execution plan |
| PLANS.md | MODIFY | Register active closed-loop plan |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Add live PQX + certification handoff/write-back orchestration |
| spectrum_systems/orchestration/pqx_handoff_adapter.py | CREATE | Keep PQX handoff logic isolated from cycle state machine |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add write-back fields required for live execution and certification tracking |
| contracts/examples/cycle_manifest.json | MODIFY | Keep canonical example aligned with manifest schema |
| contracts/standards-manifest.json | MODIFY | Publish updated cycle manifest schema version metadata |
| tests/test_cycle_runner.py | MODIFY | Add end-to-end and blocked-path integration coverage |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document live closed-loop behavior and terminal states |
| docs/runbooks/cycle_runner.md | MODIFY | Operator guidance for live handoff and fail-closed behavior |
| docs/roadmap/system_roadmap.md | MODIFY | Keep compatibility mirror row aligned with closed-loop status |
| docs/reviews/autonomous_execution_closed_loop_slice_report.md | CREATE | Repo-native implementation status/review artifact |

## Contracts touched
- `cycle_manifest` (additive extension)
- `contracts/standards-manifest.json` (version metadata update for `cycle_manifest`)

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_module_architecture.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign cycle state vocabulary outside existing control-plane semantics.
- Do not reimplement PQX internals; invoke canonical runtime seam.
- Do not reimplement GOV-10 certification internals; invoke canonical governance seam.
- Do not create a parallel orchestration subsystem.

## Dependencies
- `docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-2026-03-30.md` foundation slice remains baseline.
- Existing seams must remain authoritative:
  - `spectrum_systems.modules.runtime.pqx_slice_runner.run_pqx_slice`
  - `spectrum_systems.modules.governance.done_certification.run_done_certification`
