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

## TLS evidence refresh after test changes
- Generator commands run:
  - `python scripts/build_tls_dependency_priority.py --out artifacts/tls --top-level-out artifacts --candidates ""`
  - `python scripts/generate_ecosystem_health_report.py`
- Regenerated artifact path: `artifacts/tls/system_evidence_attachment.json`.
- Why artifact changed: latest AGL-01 test updates added discoverable evidence and TLS attachment now includes `tests/test_agent_core_loop_proof.py` in multiple system evidence sets.
- Validation commands run:
  - `python scripts/run_contract_enforcement.py`
  - `python -m pytest tests/test_agent_core_loop_proof.py -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`

## Contract mismatch fix
- Exact failing rule addressed: repo-mutating semantic consistency and cross-surface contract alignment between examples, schema, builder, and tests.
- Files changed:
  - `contracts/examples/agent_core_loop_run_record.blocked.example.json`
  - `tests/test_agent_core_loop_proof.py`
- Fix preserves fail-closed behavior:
  - contract remains strict (`present` requires refs; missing statuses require reason codes; core-loop-complete guard remains)
  - blocked example now explicitly models non-repo-mutating observation-only gap case (`repo_mutating=false`) rather than violating repo-mutating AEX/PQX expectations
  - builder output is now asserted against schema directly in tests
- Validation commands run:
  - `python scripts/run_contract_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
  - `python scripts/run_contract_enforcement.py`
  - `pytest tests/test_agent_core_loop_proof.py -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
- Final result: contract preflight passed with `status=passed` and `strategy_gate_decision=ALLOW` (no `contract_mismatch` block).

## TLS evidence determinism cleanup
- Diagnosis: stale artifact, not generator nondeterminism.
- Files changed:
  - `artifacts/tls/system_evidence_attachment.json`
  - `docs/reviews/AGL-01_agent_core_loop_final_report.md`
- Generator commands run (twice):
  - `python scripts/build_tls_dependency_priority.py --out artifacts/tls --top-level-out artifacts --candidates ""`
  - `python scripts/generate_ecosystem_health_report.py`
- Second-run stability result: identical structural diff after both runs (no additional drift introduced on second run).
- Evidence confirmation: regenerated attachment includes `tests/test_agent_core_loop_proof.py` in discovered evidence lists.
- Tests added/updated: none required (generator behavior observed deterministic in repeated runs).
- Final validation commands:
  - `python scripts/run_contract_enforcement.py`
  - `python -m pytest tests/test_agent_core_loop_proof.py -q`
  - `python -m pytest tests/ -k "tls or evidence_attachment or agent_core_loop" -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`

## Remaining contract mismatch cleanup
- Diagnosis artifact status at rerun: `contract_preflight_report.status=passed`; no active `contract_mismatch` block artifacts were produced (`block_bundle` empty in preflight result).
- Exact mismatch summary from diagnosis surfaces:
  - failing file: none (resolved)
  - expected contract rule: fail-closed schema+example+builder alignment
  - actual value: all evaluated contract/example/producer/consumer failure lists empty
  - JSON path evidence: `schema_example_failures=[]`, `producer_failures=[]`, `consumer_failures=[]`
  - repair candidate: none required in this rerun
- Root cause addressed: residual risk of unsupported upstream artifact shape in builder path; added regression proving unsupported shape emits unknown/missing evidence instead of crashing.
- Files changed:
  - `tests/test_agent_core_loop_proof.py`
  - `docs/reviews/AGL-01_agent_core_loop_final_report.md`
- Why fix preserves fail-closed behavior:
  - unsupported source artifacts now explicitly validated as non-crashing and fail-closed (`unknown/missing` + reason_codes + BLOCK for repo-mutating path)
  - no schema constraints were weakened
- Regression tests added:
  - `test_builder_handles_unsupported_source_artifact_shape`
- Exact commands run:
  - `python scripts/build_preflight_pqx_wrapper.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output outputs/contract_preflight/preflight_pqx_task_wrapper.json`
  - `python scripts/run_contract_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
  - `python scripts/run_contract_enforcement.py`
  - `python -m pytest tests/test_agent_core_loop_proof.py -q`
  - `python -m pytest tests/ -k "agent_core_loop or contract_preflight or contract" -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
- Final preflight result: `status=passed`; no `contract_mismatch` failure_class.

## Contract mismatch final cleanup
- Exact diagnosis from preflight artifacts:
  - current rerun `contract_preflight_report.status=passed`
  - no block artifacts generated (`preflight_block_diagnosis_record.json`, repair-plan artifacts absent because no block)
  - residual mismatch signal came from `pytest_selection_integrity` in `contract_preflight_result_artifact.json`: `selection_integrity_decision=BLOCK` with `missing_required_targets=["tests/test_contracts.py"]`
- Root cause:
  - preflight required-surface mapping did not explicitly map new `agent_core_loop_run_record*.schema.json` files to `tests/test_contracts.py`, creating recurring contract-mismatch risk in strict preflight contexts.
- Files changed:
  - `docs/reviews/AGL-01_contract_mismatch_diagnosis.md`
  - `docs/governance/preflight_required_surface_test_overrides.json`
  - `tests/test_agent_core_loop_proof.py`
  - `docs/reviews/AGL-01_agent_core_loop_final_report.md`
- Regression test added:
  - `test_preflight_override_includes_contract_tests_for_agent_core_loop_schemas`
- Why fix preserves fail-closed behavior:
  - no schema constraints weakened
  - no contract entries removed
  - preflight is strengthened by ensuring required contract tests are selected for the new schema surfaces
- Validation commands run:
  - `python scripts/build_preflight_pqx_wrapper.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output outputs/contract_preflight/preflight_pqx_task_wrapper.json`
  - `python scripts/run_contract_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
  - `python scripts/run_contract_enforcement.py`
  - `python -m pytest tests/test_agent_core_loop_proof.py -q`
  - `python -m pytest tests/ -k "agent_core_loop or contract_preflight or contract" -q`
  - `python scripts/run_authority_shape_preflight.py --base-ref "9e495b4eb6e1bcc6d3f54741f6eebf468ba2f628" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
  - `python scripts/run_authority_leak_guard.py --base-ref "2b25f8027e2a7068313caeceffe803bb19c8a065" --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
- Final preflight result:
  - `status=passed`
  - `strategy_gate_decision=ALLOW`
  - no `contract_mismatch` block
