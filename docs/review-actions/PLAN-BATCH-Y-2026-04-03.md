# Plan — BATCH-Y — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-Y — Real-Use Shakeout + Friction Harvest

## Objective
Exercise the existing operator cycle through deterministic real-use scenarios and emit governed friction/backlog artifacts that prioritize the next smallest high-value hardening fixes.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-Y-2026-04-03.md | CREATE | Required plan-first artifact for this multi-file BATCH-Y implementation. |
| PLANS.md | MODIFY | Register active BATCH-Y plan entry. |
| contracts/schemas/operator_friction_report.schema.json | CREATE | Contract-first schema for deterministic friction-harvest report emitted by shakeout runs. |
| contracts/schemas/operator_backlog_handoff.schema.json | CREATE | Contract-first schema for prioritized operator hardening backlog handoff artifact. |
| contracts/examples/operator_friction_report.json | CREATE | Golden-path example for operator_friction_report contract. |
| contracts/examples/operator_backlog_handoff.json | CREATE | Golden-path example for operator_backlog_handoff contract. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump standards manifest version pins. |
| spectrum_systems/modules/runtime/operator_shakeout.py | CREATE | Implement deterministic BATCH-Y scenario execution, friction classification, and backlog prioritization logic on top of run_system_cycle seam. |
| scripts/run_operator_shakeout.py | CREATE | Operator CLI entrypoint for BATCH-Y shakeout artifact generation. |
| tests/test_operator_shakeout.py | CREATE | Deterministic tests for scenario execution, friction classification, backlog ranking, and schema validation. |
| tests/test_contracts.py | MODIFY | Add contract-example validation coverage for the new BATCH-Y governed artifacts. |
| docs/runtime/operator_cycle_shakeout.md | CREATE | Operator-facing process doc for running/reading system-cycle shakeout and interpreting stop conditions. |

## Contracts touched
- `contracts/schemas/operator_friction_report.schema.json` (new)
- `contracts/schemas/operator_backlog_handoff.schema.json` (new)
- `contracts/standards-manifest.json` (new contract entries + version bump)

## Tests that must pass after execution
1. `pytest tests/test_operator_shakeout.py`
2. `pytest tests/test_system_cycle_operator.py`
3. `pytest tests/test_system_integration_validator.py`
4. `pytest tests/test_roadmap_multi_batch_executor.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign PRG/RVW/CTX/TPA/PQX architecture or authority boundaries.
- Do not introduce new subsystems or external service integrations.
- Do not change roadmap execution semantics beyond narrow operator-facing hardening.

## Dependencies
- `docs/review-actions/PLAN-BATCH-U-2026-04-03.md` operator seam (`run_system_cycle`) remains the execution backbone.
- `docs/review-actions/PLAN-BATCH-Z-2026-04-03.md` core integration validation invariants remain authoritative.
