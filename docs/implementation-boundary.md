# Implementation Boundary

## Purpose
Clarify ownership between this architecture repository (spectrum-systems) and executable implementation repositories so system contracts remain stable while implementations evolve.

## Architecture Repository (spectrum-systems) Owns
- System specifications and architecture decisions (e.g., `systems/comment-resolution/interface.md`).
- Authoritative schemas and provenance guidance (`schemas/*.json`, `docs/provenance-implementation-guidance.md`).
- Error taxonomy and message patterns (`docs/error-taxonomy.md`).
- Prompt standards and evaluation definitions (`prompts/`, `eval/`).
- Shared rule packs and profiles under `rules/`.

## Implementation Repositories Own
- Executable code, pipelines, connectors, and runtime configuration.
- Local fallbacks and heuristics that operate when external rule packs are absent.
- Integration with storage, access control, and deployment concerns.

## Declarations Required in Implementation Repos
Implementation repositories MUST explicitly declare:
- `system_id` implemented (e.g., `SYS-001` Comment Resolution Engine).
- Spec, schema, provenance guidance, and error taxonomy versions targeted.
- Rule profile/version in use (or explicit statement that local defaults are active).

## Current Mapping for SYS-001
- Architecture source: `spectrum-systems` (this repo)
- Implementation repo: `comment-resolution-engine`
- Spec: `systems/comment-resolution/interface.md`
- Schemas: `schemas/comment-schema.json`, `schemas/issue-schema.json`, `schemas/provenance-schema.json`
- Provenance guidance: `docs/provenance-implementation-guidance.md`
- Error taxonomy: `docs/error-taxonomy.md`
- Rule pack (starter): `rules/comment-resolution/`
- Evaluation assets: `eval/comment-resolution/`

Implementation repositories SHOULD keep these declarations in code or metadata to preserve traceability across releases.
