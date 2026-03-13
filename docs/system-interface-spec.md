# System Interface Specification

Use this template when defining or reviewing a system. Every system must expose a minimal, deterministic contract that other systems can rely on.

## Required Sections
- **Purpose**: One paragraph on the workflow bottleneck solved and the decision supported.
- **Inputs**: Enumerate required inputs with schemas, allowed formats, and validation rules.
- **Outputs**: Enumerate outputs with schemas, lineage requirements, and review status expectations.
- **Interfaces**: Describe APIs, file drops, or queue contracts the system will provide in implementation repos.
- **Dependencies**: Upstream systems, datasets, prompts, rules, and models required to run.
- **Validation & Evaluation**: How correctness, determinism, and traceability are tested; link to `eval/` assets.
- **Failure Modes**: Blocking validation rules and expected error classes.
- **Versioning**: How the system surfaces interface versions and how breaking changes are communicated.

## Minimum Interface Contract
- Accepts inputs that conform to the schemas referenced in `schemas/`.
- Emits outputs that include provenance and reproducibility metadata (see `docs/reproducibility-standard.md`).
- Emits explicit validation results; failures must be blocking and informative.
- Provides a changelog for prompts, rules, and schemas that affect outputs.

## Review Checklist
- Inputs/outputs listed with schemas and required fields.
- Traceability metadata required and enforced.
- Human review steps identified with clear entry/exit criteria.
- Evaluation plan linked and scoped to cover high-risk behaviors.
- Dependencies on other systems or datasets are explicit and versioned.

## Where to Declare
- Each system keeps `interface.md` under `systems/<system>/`.
- Shared expectations live here; implementation repos must not diverge without updating this spec and associated schemas.
