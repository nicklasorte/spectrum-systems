# PLAN-GRC-FOUNDATION-2026-04-10

**Primary Type:** BUILD

## Scope
Deliver governed repair-loop closure foundation for GRC-01/02/03/04 without creating a new system and without ownership duplication.

## Canonical alignment
- `README.md`
- `docs/architecture/system_registry.md`

## Planned execution
1. Inspect and extend repo-native contract/runtime surfaces already used for AUT seams, failure diagnosis, and review/fix artifacts.
2. Implement GRC-01 additive slice failure-surface declarations in `slice_registry` with fail-closed validation in the runtime loader.
3. Implement GRC-02/GRC-03/GRC-04 foundation utilities for artifact readiness gating, canonical failure packetization (RIL-owned interpretation), bounded repair candidate generation (FRE-owned), CDE continuation input derivation, and TPA repair gating input derivation.
4. Publish schema-backed contracts and examples for new governed artifacts; update standards manifest version registry.
5. Add focused tests anchored to AUT-05/AUT-07/AUT-10 mismatch classes and ownership boundaries.
6. Produce review and delivery governance artifacts documenting ownership safety, representability, and remaining gaps.
7. Run targeted and required contract checks; commit and open PR artifact.

## Non-goals
- No prompt-driven execution fallback.
- No new runtime authority system.
- No auto-repair execution loop expansion beyond bounded foundation inputs.
