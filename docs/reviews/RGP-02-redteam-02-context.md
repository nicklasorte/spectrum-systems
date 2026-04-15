# RGP-02 REDTEAM-02 — context and intake contract attack review

## REDTEAM-02 — attack context
Owner: MNT + non-authoritative

Build:
- schema:
  - No new red-team schema; markdown review artifact used.
- functionality:
  - Attacked bounded-family context surfaces with stale/malformed/poisoned context payload variants.
  - Verified missing required fields in `context_preflight_result` and malformed translation/normalization artifacts trigger validation failure.
- integration:
  - Exercised through `spectrum_systems.governance.rgp02_gate.validate_bounded_family_inputs` path and contract validators.
- control/eval:
  - Fail-closed behavior observed for missing and invalid context-adjacent artifacts.
- tests:
  - `tests/test_rgp02_gate.py::test_gate_blocks_malformed_artifact`
  - `tests/test_rgp02_contract_surface.py::test_rgp02_contracts_fail_closed_when_required_field_missing`

Findings:
1. Missing contract artifacts correctly block with deterministic reason code.
2. Malformed context preflight artifacts correctly block and do not degrade to warnings.
3. Unknown contract names were blocked as invalid via fail-closed default.

Definition of done:
- Concrete findings captured.
- Findings mapped to executable tests.
