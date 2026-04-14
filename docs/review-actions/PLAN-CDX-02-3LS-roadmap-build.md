# PLAN — CDX-02 3LS Roadmap Build

Primary type: `BUILD`

## Intent
Implement a deterministic, registry-safe 3LS roadmap execution surface with explicit ownership classification, fail-closed validation, and non-authority guarantees for CRS/MGV/AIL synthesis while preserving canonical owner boundaries.

## Canonical owner + step mapping

All roadmap steps are mapped to exactly one owner in `docs/governance/cdx_02_3ls_roadmap.json` and validated by `spectrum_systems/modules/governance/cdx_02_roadmap_guard.py`.

- 3LS-01..03 → `CON`
- 3LS-04..05 → `CTX`
- 3LS-06,08 → `EVL`
- 3LS-07 → `DAT`
- 3LS-09 → `JDX`
- 3LS-10 → `JSX`
- 3LS-11 → `PRX`
- 3LS-12 → `POL`
- 3LS-13 → `REL`
- 3LS-14 → `PRM`
- 3LS-15 → `ROU`
- 3LS-16 → `OBS`
- 3LS-17 → `LIN`
- 3LS-18 → `REP`
- 3LS-19..20 → `CRS`
- 3LS-21 → `SEC`
- 3LS-22 → `CAP`
- 3LS-23 → `DRT`
- 3LS-24 → `HNX`
- 3LS-25 → `HIT`
- 3LS-26 → `RUX`
- 3LS-27..28 → `AIL`
- 3LS-29 → `RSM`
- 3LS-30 → `SCH`
- 3LS-31 → `XRL`
- 3LS-32 → `CAL`
- 3LS-33 → `CVX`
- 3LS-34..35,41 → `CHX`
- 3LS-36,42 → `FRE`
- 3LS-37 → `ENT`
- 3LS-38,44 → `PRG`
- 3LS-39..40 → `MGV`
- 3LS-43 → `CDE`

## Files / seams touched
- Governance artifacts: `docs/governance/cdx_02_3ls_roadmap.json`, `docs/governance/cdx_02_3ls_roadmap.schema.json`.
- Guard runtime: `spectrum_systems/modules/governance/cdx_02_roadmap_guard.py`, `scripts/run_cdx_02_roadmap_guard.py`.
- Runtime validators: `spectrum_systems/modules/runtime/next_phase_governance.py`.
- Tests: `tests/test_cdx_02_roadmap_guard.py`, `tests/test_next_phase_governance.py`.
- Review artifacts: `docs/reviews/CDX-02_*`.

## Fail-closed behavior
- Missing/duplicate steps, invalid owner mapping, non-canonical authority source, invalid classification, or unauthorized new-owner declaration => `BLOCK`.
- CRS/MGV authority leakage in roadmap declaration => `BLOCK`.
- AIL synthesized trust posture being interpreted as authoritative => blocked by runtime non-authority validator tests.

## Registry-safety checks
- Validate roadmap against canonical system registry acronyms.
- Permit true net-new owners only: `CRS`, `MGV`.
- Force one primary owner per step; dependencies are non-owning.
- Emit deterministic violations compatible with SRG fail-closed posture.
