# Contract Versioning Policy

Canonical artifact contracts follow semantic versioning to keep downstream engines stable and reproducible.

## Version semantics
- `MAJOR.MINOR.PATCH`
- Breaking changes increment `MAJOR` (field removals/renames, incompatible type changes, required field additions).
- Backward-compatible additions increment `MINOR` (new optional fields, enum extensions with defaults).
- Documentation-only clarifications that do not change validation increment `PATCH`.

## Compatibility expectations
- Downstream repos must pin to a `MAJOR.MINOR` series and tolerate `PATCH` changes.
- A new `MAJOR` requires coordinated updates to dependent schemas, prompts, workflows, and evaluators before adoption.
- Deprecated fields stay documented until the next `MAJOR` to preserve compatibility.

## Publication rules
- Spectrum Systems publishes authoritative contracts in `contracts/schemas/` and tracks active versions in `contracts/standards-manifest.json`.
- Changes must update the manifest, examples, and related docs in `contracts/docs/`.
- Record notable changes in `CHANGELOG.md` and reference affected systems in `SYSTEMS.md` when applicable.
- system-factory mirrors only published, manifest-listed contracts into scaffolded repos.
