# AGL-01 Contract Mismatch Diagnosis

## Source artifacts inspected
- `outputs/contract_preflight/contract_preflight_report.json`
- `outputs/contract_preflight/contract_preflight_report.md`
- `outputs/contract_preflight/contract_preflight_result_artifact.json`
- `outputs/contract_preflight/preflight_block_diagnosis_record.json` *(not generated in current rerun because preflight status is passed)*
- `outputs/contract_preflight/preflight_repair_plan_record.json` *(not generated in current rerun because preflight status is passed)*
- `outputs/contract_preflight/failure_repair_candidate_artifact.json` *(not generated in current rerun because preflight status is passed)*
- `outputs/contract_preflight/preflight_repair_result_record.json` *(not generated in current rerun because preflight status is passed)*

## Diagnosis summary
- Failing file: none in current rerun.
- Expected contract: contract/example/builder alignment under fail-closed schema rules for `agent_core_loop_run_record`.
- Actual contract: preflight status `passed`; no schema, producer, fixture, or consumer failures.
- JSON pointer / field path evidence:
  - `contract_preflight_report.json#/schema_example_failures = []`
  - `contract_preflight_report.json#/producer_failures = []`
  - `contract_preflight_report.json#/consumer_failures = []`
- Exact reason code: none active in current rerun (no block bundle).
- Repair candidate recommendation: `required evaluation mapping for changed governance/runtime/test surfaces` (from `recommended_repair_areas`).

## Residual risk identified
The preflight result artifact includes:
- `pytest_selection_integrity.selection_integrity_decision = BLOCK`
- `missing_required_targets = ["tests/test_contracts.py"]`

This indicates a deterministic test-selection mapping gap (not a schema syntax issue), and is the remaining surface to repair to prevent recurrence of `contract_mismatch` in stricter preflight modes.
