# Canonical schema authority designation

Status: Accepted

Date: 2026-03-16

## Context
`spectrum-systems` contains two schema directories:

- `contracts/schemas/` — fifteen schemas (as of 2026-03-16) covering the full governed artifact contract library: meeting minutes, comment resolution matrix, program brief, study readiness assessment, decision log, risk register, assumption register, milestone plan, next best action memo, provenance record, external artifact manifest, working paper input, reviewer comment set, artifact envelope, and the spreadsheet contract.
- `schemas/` — nine schemas covering structural data shapes used within spectrum-systems for internal data records and system-level metadata: comment, issue, provenance, assumption, study-output, precedent, compiler-manifest, artifact-bundle, and diagnostics.

The 2026-03-16 governance constitution deep review (finding `[F-4]`, structural gap `[G3]`) identified that downstream implementation repositories could not determine which directory to import from without consulting multiple documents. The dual-track had no canonical designation, no migration path for overlapping schemas (provenance, assumption), and no machine-readable boundary between governed contract schemas and supplemental structural schemas.

The risk assessment rated this Medium/Medium: as the ecosystem scales to five or more implementation repos, schema drift between directories will be undetectable and a breaking change in one location may not propagate to the other.

## Decision
Designate schema authority as follows:

| Directory | Authority | Scope |
| --- | --- | --- |
| `contracts/schemas/` | **Canonical** for governed artifact contracts | All schemas that correspond to a published contract in `contracts/standards-manifest.json`; downstream repos must import and pin these schemas |
| `schemas/` | **Supplemental** for non-contract structural schemas | Internal data shapes, data-lake records, and system-level metadata not governed as artifact contracts; used within spectrum-systems and by downstream repos when no corresponding contract schema exists |

**Import rule for downstream repos:** Always import governed artifact contract schemas from `contracts/schemas/`. Import supplemental structural schemas from `schemas/` only when no corresponding schema exists in `contracts/schemas/`.

**Migration rule:** Any schema in `schemas/` that matures to the point where it defines a governed artifact contract must be formally promoted to `contracts/schemas/` and added to `contracts/standards-manifest.json`. Until that promotion, the schema is not governed under the contract versioning policy in `CONTRACT_VERSIONING.md`. Promotion requires an architecture review and a new contract entry in the standards manifest.

**Overlap resolution:** Where both directories contain coverage of similar concepts (e.g., provenance fields appear in both `schemas/provenance-schema.json` and `contracts/schemas/provenance_record.schema.json`), the `contracts/schemas/` version is canonical for use in governed artifact contracts. The `schemas/` version may remain for internal structural use as long as it is clearly documented as supplemental.

## Consequences
- All future governed artifact contracts must be added to `contracts/schemas/` and registered in `contracts/standards-manifest.json`; adding them only to `schemas/` is not compliant.
- Downstream repo governance declarations must pin schemas from `contracts/schemas/` for all governed contract types; pins referencing `schemas/` for governed contract types will be flagged as non-compliant in Phase 2 automation.
- `CONTRACTS.md` is the authoritative public-facing declaration of this schema authority designation; `schemas/README.md` reinforces it for the supplemental directory.
- Schema promotion events (from `schemas/` to `contracts/schemas/`) must be logged as breaking changes if downstream repos were importing from `schemas/` and must follow the versioning policy in `CONTRACT_VERSIONING.md`.
- The policy engine (`governance/policies/run-policy-engine.py`) should be extended to validate that governance declarations only pin `contracts/schemas/` paths for governed contract types.

## Alternatives considered
- **Merge all schemas into a single directory.** Rejected because governed artifact contracts and internal structural schemas have different governance requirements, versioning policies, and intended consumers. Merging would obscure these distinctions and apply heavy contract-versioning overhead to lightweight internal schemas.
- **Deprecate `schemas/` and migrate all schemas to `contracts/schemas/`.** Rejected because several schemas in `schemas/` (compiler-manifest, artifact-bundle, diagnostics, precedent) have not been promoted to governed artifact contracts and do not need the overhead of the full contract governance lifecycle. Forced promotion without readiness would inflate the contract registry with under-governed schemas.
- **No formal designation; rely on documentation to guide imports.** Rejected as the status quo that produced the dual-track ambiguity identified in `[G3]`. Without a canonical designation, the ambiguity scales with the ecosystem.

## Related artifacts
- `contracts/schemas/` — canonical governed contract schema directory
- `schemas/` — supplemental structural schema directory
- `schemas/README.md` — schema authority statement and import rules for the supplemental directory
- `CONTRACTS.md` — public-facing canonical schema authority declaration
- `contracts/standards-manifest.json` — versioned registry of all governed artifact contracts
- `CONTRACT_VERSIONING.md` — versioning policy for governed contract schemas
- `docs/reviews/2026-03-16-governance-constitution-deep-review.md` — findings F-4, G3, R3
- `ADR-006-governance-manifest-policy-engine.md` — governance manifest and policy engine model
