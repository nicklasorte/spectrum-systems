# System Registry Missing Systems Alignment Review

## Scope
- Canonical target: `docs/architecture/system_registry.md`.
- Inputs audited: `README.md`, `REPO_MAP.md`, `SYSTEMS.md`, `docs/system-registry.md`, `docs/systems-registry.md`, all files under `docs/architecture/`, and relevant reviews/ADRs under `docs/reviews/` and `docs/adr/`.

## Systems already present in the canonical registry
- AEX
- PQX
- HNX
- TPA
- MAP
- RDX
- FRE
- RIL
- RQX
- SEL
- CDE
- TLC
- PRG
- SIV (reserved/not present)

## Newly added placeholders
- **LCE** (Lifecycle Control Enforcement)
  - Added because lifecycle transition enforcement is a concrete control-plane seam with canonical transition/state rules.
- **ABX** (Artifact Bus eXchange)
  - Added because Artifact Bus is defined as a platform-wide required transfer seam with schema-governed messages.
- **DBB** (Data Backbone)
  - Added because Data Backbone is a platform-wide substrate with required governed artifact records.
- **SAL** (Source Authority Layer)
  - Added because source precedence + obligation indexing is defined as canonical governance behavior.
- **SAS** (Source Authority Sync)
  - Added because deterministic retrieve/materialize/index + fail-closed completeness checks are explicitly defined.
- **SHA** (Shared Authority)
  - Added because shared primitive ownership boundaries are explicitly defined and enforced.
- **RAX** (Runtime Assurance eXchange)
  - Added because the canonical registry referenced RAX in a governed boundary note without a system definition, and architecture/review surfaces repeatedly rely on the RAX artifact seam.

## Items considered but not added
- **Signal Extraction Model**
  - Not added: treated as a model/specification surface scoped to Meeting Minutes extraction behavior, not a cross-platform ownership subsystem.
- **Review → Judgment Bridge**
  - Not added: explicitly marked design-only/future output surface and currently non-authoritative.
- **Autonomous Execution Loop**
  - Not added: documented as a behavior/composition over canonical systems rather than a separate owner system.
- **Lifecycle Enforcement**
  - Added as LCE placeholder (therefore no longer in this excluded list).
- **Shared Authority layer**
  - Added as SHA placeholder (therefore no longer in this excluded list).

## Acronym collision check result
- Checked canonical map and system definitions for duplicate 3-letter acronyms.
- Result: **no collisions found** across existing and newly added entries.

## Unresolved ambiguity
- **Placeholder boundary depth:** ABX/DBB/SAL/SAS/SHA/LCE are intentionally documented as placeholder seams to keep authority with existing canonical owners while still naming repeated subsystem surfaces.
- **RDX maturity detail:** RDX is canonical and now complete in definition fields, but implementation depth is still primarily governance/adapter-level in docs.
