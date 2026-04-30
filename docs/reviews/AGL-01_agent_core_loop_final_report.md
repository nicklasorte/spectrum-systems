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
