# AGL-01 Agent Core Loop Final Report

- Added `agent_core_loop_run_record` contract and examples for codex/claude/blocked cases.
- Added deterministic builder + CLI to produce artifact-backed loop proof records.
- Wired rollup path by producing artifacts under `artifacts/agent_core_loop/` and enabling downstream consumption.
- Added tests for schema validation, present-without-refs failure, and BLOCK outcome for missing AEX/PQX.
- Remaining gap: broaden parser coverage for EVL/TPA/CDE/SEL source families.
- Next recommended fix: add artifact resolvers for PR gate/preflight outputs and add dashboard panel assertions.

## Authority-shape cleanup
- Removed stale reason codes: `legacy_cde_gap_code` and `legacy_sel_gap_code`.
- Replaced with AGL-safe terms: `cde_signal_missing` and `sel_signal_missing`.
- Ran authority preflight command: `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`.
- Final authority-shape violation count: 0.
- Tests run: `python -m pytest tests/test_agent_core_loop_proof.py -q` and `python scripts/run_contract_enforcement.py`.


## Authority leak cleanup
- Removed forbidden values from AGL-owned text and example reason codes.
- Replacement values used: `cde_signal_missing` and `sel_signal_missing`.
- Authority leak guard result: pass (`violation_count: 0`).
- Authority-shape preflight result: pass (`violation_count: 0`).
- Tests run: `python -m pytest tests/test_agent_core_loop_proof.py -q` and `python scripts/run_contract_enforcement.py`.

## TLS artifact regeneration
- Ran generator commands:
  - `python scripts/build_tls_dependency_priority.py --out artifacts/tls --top-level-out artifacts --candidates ""`
  - `python scripts/generate_ecosystem_health_report.py`
- Regenerated artifact path: `artifacts/tls/system_evidence_attachment.json`.
- Drift reason: AGL-01 introduced new discovered surfaces (`spectrum_systems/modules/runtime/agent_core_loop_proof.py` and `docs/review-actions/AGL-01_fix_actions.md`) and TLS evidence attachment was stale.
- No TLS check was weakened or bypassed; artifact was regenerated via canonical generators.
- Validation commands run:
  - `python scripts/run_contract_enforcement.py`
  - `python -m pytest tests/test_agent_core_loop_proof.py -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`

## Contract preflight schema cleanup
- Exact schema violation from preflight: `schema_example_failures` reported missing schema files for example-derived names (`agent_core_loop_run_record.blocked/claude/codex`), specifically: `Schema not found: contracts/schemas/agent_core_loop_run_record.<variant>.schema.json`.
- Files changed:
  - `contracts/schemas/agent_core_loop_run_record.schema.json`
  - `contracts/schemas/agent_core_loop_run_record.blocked.schema.json`
  - `contracts/schemas/agent_core_loop_run_record.claude.schema.json`
  - `contracts/schemas/agent_core_loop_run_record.codex.schema.json`
  - `tests/test_agent_core_loop_proof.py`
- Why fix preserves fail-closed behavior:
  - canonical schema remains strict with `additionalProperties: false`
  - `present` still requires non-empty `artifact_refs`
  - non-present statuses still require reason codes
  - added `core_loop_complete=true` guard requiring all core leg statuses to be `present` with evidence refs
- Validation commands run:
  - `python scripts/build_preflight_pqx_wrapper.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output outputs/contract_preflight/preflight_pqx_task_wrapper.json`
  - `python scripts/run_contract_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
  - `python scripts/run_contract_enforcement.py`
  - `python -m pytest tests/test_agent_core_loop_proof.py -q`
  - `python -m pytest tests/ -k "agent_core_loop or contract" -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
- Final contract preflight result: `status=passed`, `strategy_gate_decision=ALLOW`, no schema_violation block.
