# RGP-02 FIX-02 — context red-team fix closure

## FIX-02 — fix context red-team findings
Owner: CTX + authoritative

Build:
- schema:
  - Added explicit translation/normalization context-intake contracts to prevent silent raw-input pass-through.
- functionality:
  - Added deterministic fail-closed gate implementation for bounded-family required artifacts.
- integration:
  - Wired gate helper for bounded-family readiness input validation surface.
- control/eval:
  - Missing or malformed context artifacts now produce deterministic blocking reason codes.
- tests:
  - Added and passed gate + contract fail-closed tests.

Definition of done:
- All REDTEAM-02 findings closed with tests and deterministic reasons.
