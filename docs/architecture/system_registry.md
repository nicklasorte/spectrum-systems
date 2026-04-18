# System Registry (Canonical Index)

## Core rules

1. **Single-responsibility ownership**: each governed responsibility has exactly one canonical owner.
2. **No-duplication rule**: no system may implement, enforce, or shadow a responsibility owned by another system.
3. **Artifact-first execution**: required transitions must be represented as governed artifacts.
4. **Fail-closed behavior**: missing required evidence blocks progression.
5. **Promotion requires certification**: promotion is prohibited without required certification evidence.

These rules are hard boundaries for architecture, contracts, execution, and validation.

## Canonical architecture split

The registry is intentionally split to reduce semantic sprawl and keep authority boundaries explicit.

- `system_registry_core.md` — authoritative runtime spine systems plus support planes.
- `system_registry_support.md` — grouped subsystem/support families (non-peer to runtime spine authorities).
- `system_registry_reserved.md` — reserved/non-active acronyms and future seams.
- `runtime_spine.md` — hard runtime chain and BLOCK/FREEZE/ALLOW semantics.

## Runtime authority summary

Authoritative runtime spine:

**AEX → PQX → EVL → TPA → CDE → SEL**

Mandatory gate overlays:

- REP (replay)
- LIN (lineage)
- OBS (observability)

Support planes (not minimal spine authorities): TLC, FRE, RIL, PRG.

## System addition rule

A new canonical system may be added only if all of the following are proven:

1. One unique authority.
2. One clear blocking failure it prevents.
3. One enforced contract surface.
4. One tested fail-closed boundary.
5. Explicit proof it cannot be a subsystem group or artifact family.

If these are not met, the capability must remain in support families or reserved status.
