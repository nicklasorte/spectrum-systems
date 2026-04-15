# RGP-02 REDTEAM-06 — readiness gate attack review

## REDTEAM-06 — attack gates
Owner: MNT + non-authoritative

Build:
- schema:
  - No red-team schema changes.
- functionality:
  - Attacked readiness gate path using missing required artifacts, malformed schema payloads, and unknown contract requirements.
- integration:
  - Exercised fail-closed gate helper for `governed_prompt_queue` bounded-family requirements.
- control/eval:
  - Verified bypass is not possible when required artifacts are absent or invalid.
- tests:
  - `tests/test_rgp02_gate.py` full suite including replay-stability and unknown-contract block.

Findings:
1. Gate correctly blocks on missing eval summary (`missing:eval_slice_summary`).
2. Gate correctly blocks malformed context preflight payload (`invalid:context_preflight_result`).
3. Gate deterministically reproduces identical decision/reason outputs across re-runs.

Definition of done:
- Gate attack findings documented and bound to executable tests.
