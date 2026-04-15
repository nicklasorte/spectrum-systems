# RGP-02 FIX-06 — readiness gate fix closure

## FIX-06 — fix gate red-team findings
Owner: CDE + authoritative

Build:
- schema:
  - No additional schema changes required after gate attack review.
- functionality:
  - Preserved fail-closed unknown-contract handling by mapping schema lookup failures to invalid reason codes.
- integration:
  - Kept this as an input gate only; no closure/promotion authority duplication introduced.
- control/eval:
  - Replay-stable reason-code ordering enforced through deterministic sorting.
- tests:
  - Added deterministic replay test and unknown-contract adversarial blocking test.

Definition of done:
- All REDTEAM-06 findings closed with explicit tests.
