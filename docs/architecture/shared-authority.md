# Shared-Layer Authority Rules

**Status:** Active  
**Date:** 2026-03-17  
**Scope:** spectrum-systems platform — all modules  

---

## Purpose

This document defines the authoritative boundary of the `shared/` layer within the `spectrum-systems` platform. It is a binding architectural rule, not a recommendation.

Any structure or primitive defined in `shared/` is **owned exclusively by that module**. No other module may redefine, shadow, or locally duplicate these structures.

---

## What Only `shared/` May Define

The following categories of primitives are the exclusive responsibility of the `shared/` layer:

| Primitive Category | Owning Module | Notes |
| --- | --- | --- |
| **Artifact models** | `shared/artifact_models` | Canonical envelope schemas, artifact bundle structures, artifact metadata |
| **Identifier schemes** | `shared/ids` | All stable artifact, module, run, and system identifiers |
| **Lineage structures** | `shared/lineage` | Derivation records, lineage chains, source relationships |
| **Provenance structures** | `shared/provenance` | Provenance records, audit trails, generating workflow references |
| **Readiness state primitives** | `shared/readiness` | Readiness classifications, readiness assessment envelopes |

These primitives are **platform-level shared truth**. Defining equivalent structures in any other module is a boundary violation.

---

## What Other Modules Must Do

All non-shared modules (`control_plane/`, `workflow_modules/`, `domain_modules/`, `orchestration/`) must:

1. **Import** shared primitives from the appropriate `shared/` module.
2. **Reference** shared structures by their canonical names in module manifests under `authoritative_imports`.
3. **Not redefine** artifact models, ID schemes, lineage structures, provenance structures, or readiness primitives locally.
4. **Declare** in `forbidden_responsibilities` that they do not own these shared structures.

Consuming a shared primitive for local use is correct behavior. Duplicating or redefining it is a violation.

---

## What Belongs in Each Layer

### `shared/`

Authoritative platform-level primitives that every other layer depends on:

- Artifact envelope and bundle schemas
- Identifier generation and validation
- Lineage record structures
- Provenance record structures
- Readiness state primitives
- Shared adapters and utilities that other layers consume

**Rule:** Defines primitives. Does not implement domain logic or workflow logic.

### `control_plane/`

Governance, lifecycle management, and enforcement:

- Lifecycle state management and transitions
- Evaluation run management and result recording
- Work item creation, tracking, and resolution
- Contract and schema governance
- Policy enforcement
- Review system and review checkpoints
- Observability and health reporting

**Rule:** Uses shared primitives. Does not redefine them. Does not implement domain logic.

### `workflow_modules/`

Canonical workflow implementations for specific engineering workflows:

- Meeting transcript processing and minutes generation
- Comment extraction, resolution, and disposition
- Working paper review workflows
- Comment injection workflows
- Study planning workflows
- Agency question intake and processing

**Rule:** Consumes shared primitives and control_plane contracts. Does not implement domain reasoning. Does not redefine shared structures.

### `domain_modules/`

Domain-specific reasoning and knowledge:

- Frequency allocation intelligence
- Interference analysis
- Knowledge capture and institutional memory
- Regulatory reasoning
- Review prediction

**Rule:** Consumes shared primitives and workflow outputs. Does not define platform-level primitives. Domain-specific data structures are permitted within the module boundary.

### `orchestration/`

Runtime sequencing and artifact coordination:

- Pipeline execution and step sequencing
- Artifact bus and cross-module handoff
- State machine for lifecycle transitions

**Rule:** Orchestrates modules. Does not implement module-level logic. Does not redefine shared primitives.

---

## Enforcement

These rules are enforced by:

1. **Module manifests** — every module declares `authoritative_imports` and `forbidden_responsibilities` in its manifest file.
2. **Validation script** — `scripts/validate_module_architecture.py` checks all manifests for compliance and detects schema redefinition violations.
3. **CI gate** — the validation script runs on every pull request and push via `.github/workflows/artifact-boundary.yml`.

Violations are reported as CI failures with actionable messages identifying the module, the rule violated, and the offending path.

---

## Adding New Shared Primitives

Adding a new primitive to the `shared/` layer is a **serialized, coordinated change**. It must not be done in parallel with other shared-layer changes.

Steps:
1. Propose the new primitive in a design review or architecture decision.
2. Add the primitive to the appropriate `shared/` module.
3. Update the module manifest for that module.
4. Update all consumer module manifests to reference the new primitive in `authoritative_imports`.
5. Run the validation script locally before merging.

See `docs/architecture/module-pivot-roadmap.md` (Serialized Work section) for the rationale.

---

## References

- `schemas/module-manifest.schema.json` — module manifest schema
- `docs/module-manifests/` — all module manifests
- `scripts/validate_module_architecture.py` — enforcement script
- `docs/architecture/module-pivot-roadmap.md` — module-first architecture roadmap
