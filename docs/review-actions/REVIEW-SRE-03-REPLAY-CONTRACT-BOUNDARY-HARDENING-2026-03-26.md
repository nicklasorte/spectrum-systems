# Review Artifact — SRE-03 Replay Contract Boundary Hardening — 2026-03-26

## Invariant
Canonical governed artifact contracts must be constructed through shared builders or authoritative runtime builders, not duplicated local dict shapes.

## Replay-adjacent violations addressed in this slice
1. **Local observability fixture drift in error-budget tests**
   - Replaced hand-maintained `observability_metrics` dict shape in `tests/test_error_budget.py` with a shared canonical builder seeded from canonical contract examples.
2. **Regression harness stale replay shape acceptance risk**
   - Added explicit fail-closed test coverage that legacy replay payload shapes are rejected by schema validation before regression comparison proceeds.

## Out of scope (explicit)
- Repo-wide direct schema file read warnings from contract-boundary audit.
- Non replay-adjacent contract-boundary findings.
- Control-loop/replay runtime semantic changes.
- Any schema version or required-field loosening.
