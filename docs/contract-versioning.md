# Contract Versioning and Compatibility

Define how artifact schemas evolve so downstream engines remain stable and reproducible.

## Required version fields
- `artifact_version` — version of the produced artifact instance.
- `schema_version` — version of the JSON Schema used to validate the artifact.
- `standards_version` — czar standards release that governs this artifact.
All artifact schemas must include these fields and downstream systems must populate them to preserve traceability.

## Change types
- **compatible** — validation-neutral changes such as documentation clarifications, improved examples, or metadata defaults that do not alter required fields. Publish as a patch bump; downstream engines should accept these without repinning.
- **minor change** — backward-compatible shape changes such as adding optional fields, extending enums with safe defaults, or adding optional metadata blocks. Publish as a minor bump; engines may opt in when ready but older payloads remain valid.
- **breaking change** — any change that removes/renames fields, adds required fields, changes types, or alters semantics in a way that invalidates existing payloads. Publish as a major bump and retain the prior major until dependent engines migrate.

## Compatibility expectations
- Contracts follow semantic versioning; consumers pin to `MAJOR.MINOR` and permit patch updates within that series.
- New releases must preserve validation compatibility within a major series; deprecations stay documented until the next major.
- When contracts change, update schemas, examples, manifests, and prompts together so engines encounter deterministic behavior.

## Handling breaking changes
- Propose the change with impact analysis and migration steps; submit to the architecture review process defined in `docs/design-review-standard.md` before publishing.
- After approval, publish a new major version in `contracts/standards-manifest.json`, keep validation fixtures for the prior major, and document migration guidance and deprecations.
- Do not remove prior major schemas until all registered consumers have migrated or a sunset date has been approved.

## Operational engine upgrades
- Engines pin to `contracts/standards-manifest.json` and declare the contract versions they support.
- For compatible and minor changes, add fixture tests, update pins, and roll out without breaking existing runs.
- For breaking changes, stage dual-read/write or adapters where possible, run evaluation against representative artifacts, then switch pins to the new major and archive the old major only after successful validation in production-like environments.
- Capture upgrade steps and verification results so downstream pipelines can reproduce and audit the transition.
