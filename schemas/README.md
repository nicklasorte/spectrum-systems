# Schema Directory Guide

This directory contains authoritative schemas that anchor every system and workflow. Schemas define the contracts that keep automation outputs deterministic and reviewable.

## Schema Categories

- **Root Schemas**: System-level records such as `comment-schema.json`, `issue-schema.json`, `precedent-schema.json`, and `assumption-schema.json` that define the primary objects exchanged between systems.
- **Data Lake Schemas**: Structured dataset definitions under `data-lake/` that describe how curated data is stored for reuse.
- **Provenance Schema**: `provenance-schema.json` defines the metadata fields required for traceability, including source, lineage, workflow step, reviewer, and version.

## Schema Evolution

- Use `MAJOR.MINOR` versioning.
- Breaking changes (field removals, renames, or type changes) must increment `MAJOR`.
- Additive, backward-compatible fields increment `MINOR`.
- Deprecated fields should remain documented with clear deprecation notes to preserve backward compatibility.

## Schema Governance

Governance expectations are described in `docs/schema-governance.md`. Schema changes should reference that guidance and ensure downstream systems, prompts, and evaluation harnesses are updated in lockstep.
