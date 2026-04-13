# PLAN-RSM-OPX-001

Prompt type: BUILD

## Scope
Implement RSM foundation in executable code and wire non-authoritative reconciliation inputs for CDE consumption while preserving canonical owner boundaries.

## Canonical alignment
- Preserve `AEX -> TLC -> TPA -> PQX` execution lineage.
- Keep RSM strictly preparatory: desired/actual state comparison, divergence classification, reconciliation preparation, and portfolio aggregation.
- Keep closure authority in CDE and enforcement authority in SEL.

## Planned changes
1. Add governed RSM runtime module with deterministic builders/validators for desired state, actual state, delta, divergence, reconciliation plan, portfolio snapshot, freshness checks, guardrails, RIL-input contract checks, stability control, divergence ranking, conflict density, and operator-overload shaping.
2. Add contract schemas and examples for RSM artifacts and register them in standards manifest.
3. Add deterministic tests covering non-authoritative behavior, authority-leak prevention, desired/actual/delta/divergence/reconciliation/portfolio validity, freshness handling, anti-thrashing, top-K prioritization, and CDE-authority-preserving integration.
4. Add implementation review artifact documenting intent, boundaries, tests, and remaining gaps.

## Out of scope
- Replacing CDE, SEL, PQX, TPA, or RIL authority roles.
- UI changes.
- Unrelated refactors.
