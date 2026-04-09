# System Registry Boundary Hardening Review

## Prompt type
REVIEW

## Scope
BATCH-SYS-ENF-01 hardening of `docs/architecture/system_registry.md` plus machine-checkable drift enforcement.

## What changed
- Hardened role boundaries for TLC, CDE, RQX, RIL, FRE, TPA, SEL, PRG, AEX, and MAP in the canonical registry.
- Removed TLC ownership of promotion-readiness evaluation artifacts and constrained TLC to orchestration/routing and non-authoritative handoff classification.
- Elevated CDE ownership with explicit `promotion_readiness_decisioning` under closure-state authority.
- Clarified RQX as queue execution only, with explicit must-not ownership of interpretation semantics and repair diagnosis/planning.
- Clarified MAP to mediation/projection formatting only, with explicit non-overlap guardrails against RIL/RQX/CDE.
- Added a fail-closed validator (`scripts/validate_system_registry_boundaries.py`) that parses registry system definitions and blocks boundary drift.
- Added deterministic tests (`tests/test_system_registry_boundary_enforcement.py`) to enforce successful baseline validation and key failure modes.

## Overlaps tightened
- **TLC vs CDE/TPA/RIL/AEX**: TLC no longer owns promotion gate evaluation and is explicitly barred from closure authority, policy admissibility, review interpretation, and admission ownership.
- **RQX vs RIL/FRE/CDE**: RQX now has explicit must-not rules blocking interpretation semantics ownership, repair diagnosis ownership, and closure authority.
- **SEL vs TPA/RIL**: SEL explicitly cannot reinterpret policy admissibility or review semantics.
- **PRG vs runtime control**: PRG explicitly cannot influence runtime execution authority or admission decisions.
- **MAP vs RIL**: MAP now explicitly constrained to formatting/projection mediation, not semantic interpretation.

## Ambiguities that remain
- MAP’s durable necessity remains limited; current hardening keeps it bounded but does not yet prove long-term architectural necessity beyond projection formatting.
- RDX and HNX interactions with expanded runtime controls are not re-scoped in this slice to avoid architecture redesign outside declared scope.

## Gaps intentionally not expanded into new systems
- No new system acronyms were introduced.
- Any potential additional roles (e.g., separate promotion-certification coordinator) are left as pending architecture judgment rather than being introduced without constitutional backing.
- Existing systems were tightened before breadth expansion, per strategy-control rules.

## Architecture-level judgment still required before expansion
- Whether MAP remains a durable standalone system or should be absorbed into a stricter projection-only contract surface.
- Whether roadmap-loop governance (RDX/PRG boundary) needs additional constitutional narrowing under future control-loop expansion.
- Whether further certification-layer decomposition is needed, contingent on source-authority updates and not inferred here.
