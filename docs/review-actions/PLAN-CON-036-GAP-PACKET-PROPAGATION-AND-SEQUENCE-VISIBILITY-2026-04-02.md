# Plan — CON-036 GAP-PACKET PROPAGATION AND SEQUENCE-LEVEL VISIBILITY — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-036 — PQX Gap-Packet Propagation and Sequence-Level Visibility

## Objective
Propagate governed control-surface gap packet consumption, prioritized gaps, derived PQX work items, and explicit packet influence signals through PQX slice, sequence, and cycle observability outputs as deterministic schema-validated machine-readable fields.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-036-GAP-PACKET-PROPAGATION-AND-SEQUENCE-VISIBILITY-2026-04-02.md | CREATE | Required plan-first artifact for CON-036 |
| PLANS.md | MODIFY | Register CON-036 plan in active plans table |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Emit slice-level governed control-surface visibility fields and fail-closed validation |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Propagate compact slice visibility into sequence-level execution history/state |
| spectrum_systems/orchestration/cycle_observability.py | MODIFY | Surface compact packet influence visibility at cycle status/backlog seams |
| contracts/schemas/pqx_slice_execution_record.schema.json | MODIFY | Extend governed contract with packet visibility fields |
| contracts/schemas/prompt_queue_sequence_run.schema.json | MODIFY | Extend sequence state contract with sequence-level visibility projection |
| contracts/schemas/cycle_status_artifact.schema.json | MODIFY | Extend cycle observability contract with compact control-surface visibility summary |
| contracts/schemas/cycle_backlog_snapshot.schema.json | MODIFY | Extend backlog metrics contract with control-surface visibility rollup counters |
| contracts/examples/pqx_slice_execution_record.json | MODIFY | Golden example for extended slice visibility fields |
| contracts/examples/prompt_queue_sequence_run.json | MODIFY | Golden example for extended sequence visibility fields |
| contracts/examples/cycle_status_artifact.json | MODIFY | Golden example for cycle-level compact visibility summary |
| contracts/examples/cycle_backlog_snapshot.json | MODIFY | Golden example for extended backlog visibility rollup counters |
| contracts/standards-manifest.json | MODIFY | Version bump and registration updates for changed governed contracts |
| tests/test_pqx_slice_runner.py | MODIFY | Add fail-closed + deterministic visibility propagation tests at PQX slice seam |
| tests/test_pqx_slice_continuation.py | MODIFY | Add sequence-level visibility propagation assertions |
| tests/test_cycle_observability.py | MODIFY | Add cycle-level compact visibility summary assertions |
| tests/test_contracts.py | MODIFY | Ensure updated examples and schemas validate |

## Contracts touched
- `pqx_slice_execution_record`
- `prompt_queue_sequence_run`
- `cycle_status_artifact`
- `cycle_backlog_snapshot`

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_gap_to_pqx.py`
2. `pytest -q tests/test_pqx_slice_runner.py`
3. `pytest -q tests/test_sequence_transition_policy.py`
4. `pytest -q tests/test_cycle_runner.py tests/test_cycle_observability.py`
5. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/run_contract_preflight.py --changed-path <each changed path>`
8. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign PQX execution architecture or step selection policy.
- Do not add autonomous remediation generation or heuristic inference.
- Do not introduce non-governed output artifacts when existing governed artifacts can be extended.
- Do not refactor unrelated runtime, contracts, or roadmap logic.

## Dependencies
- Existing governed `control_surface_gap_packet` and `control_surface_gap_to_pqx` seams remain authoritative inputs.
- Existing PQX slice, sequence-runner, and cycle observability execution paths remain primary propagation paths.
