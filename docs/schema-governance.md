# Schema Governance

This guide defines how schemas evolve so that downstream systems remain stable and traceable.

## Schema Versioning

- Version format: `MAJOR.MINOR`.
- Breaking changes increment `MAJOR`.
- Backward-compatible changes increment `MINOR`.

## Breaking Changes

Examples of changes that require a major version bump:
- Removing a field.
- Renaming a field.
- Changing a field type or allowed enum values in a non-backward-compatible way.

## Non-breaking Changes

Examples of changes that only require a minor version bump:
- Adding optional fields.
- Adding metadata fields that do not change existing requirements.

## Approval Process

Schema changes should be reviewed and approved before adoption by downstream systems. Impacted systems, prompts, workflows, and evaluation harnesses must be updated alongside the schema version change to preserve deterministic behavior.
