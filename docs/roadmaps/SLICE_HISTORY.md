# Slice History

- **2026-04-07 — BATCH-GOV-FIX-01**: Repaired GOV-NEXT-01-03 contract preflight BLOCK by adding deterministic wrapper coverage in `tests/test_run_prompt_with_governance.py`, preserving fail-closed governance checks and restoring preflight `strategy_gate_decision=ALLOW` for the governed prompt-enforcement change surface.
- **2026-04-07 — BATCH-GOV-FIX-02**: Established canonical `docs/governance/governed_prompt_surfaces.json`, wired `scripts/check_governance_compliance.py` and `scripts/run_contract_preflight.py` to the same governed prompt taxonomy, and added `tests/test_governed_prompt_surface_sync.py` to fail closed on prompt-surface drift.
