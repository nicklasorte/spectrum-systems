# Next Recommended Slice

## BATCH-GOV-FIX-05 — Structured Checker Diagnostics Stability

Introduce a narrow, backward-compatible structured diagnostic contract for governance checker failures (for example: stable diagnostic codes with required reference identifiers), while preserving existing fail-closed behavior and current human-readable CLI lines.

### Outcome target
- Reduces brittleness from raw string matching in governance tests.
- Keeps checker-layer and wrapper-layer assertions aligned on deterministic, machine-checkable diagnostics.
