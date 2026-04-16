# HNX-01 Red Team Review 1 — Boundary / Authority / Transition / Stop Bypass

- Verdict: **FAIL (fixed in Fix Pack 1)**
- Scope: boundary enforcement, invalid transitions, stop/freeze bypass, authority creep.

## Findings
1. Critical: invalid transition insertion accepted in stage-skip path.
2. High: stop-required transition allowed non-halt continuation.
3. High: boundary creep risk if HNX emits promotion-like outputs.
4. Medium: missing explicit regression assertion for blocked authority-smuggling names.

## Boundary analysis
HNX remains structure+signal only. It must not emit policy, promotion, or release decisions.

## Required fixes
- Enforce stage skip + stop/freeze deterministic blocks.
- Expand forbidden output overlap checks.
- Add adversarial regression tests for authority smuggling and invalid transition insertion.

## Authority boundary note
HNX remains non-authoritative beyond harness and continuity ownership; outputs are structural evidence and signals for external control/governance authorities.
