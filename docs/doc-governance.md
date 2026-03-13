# Documentation Governance

Lightweight rules to keep architecture documentation maintainable and aligned.

## Ownership
- Systems: maintained under `systems/<system>/` with clearly identified interfaces and designs.
- Standards: maintained under `docs/` with a single canonical source; avoid duplicating definitions.
- Schemas: maintained under `schemas/`; treated as authoritative contracts.

## Change Controls
- Update schemas, prompts, and evaluation assets together when interface changes occur.
- When deprecating a document, leave a pointer to the canonical replacement.
- Record material changes in `CHANGELOG.md` with dates and scope.
- Keep filenames predictable (`overview.md`, `interface.md`, `design.md`, `evaluation.md`, `prompts.md`, `README.md`).

## Review Expectations
- Check new docs against `docs/system-philosophy.md` and `docs/system-interface-spec.md`.
- Confirm references to schemas and prompts use explicit versions.
- Run the checklist in `docs/repo-maintenance-checklist.md` after large edits.

## Terminology
- Use the canonical terms in `docs/terminology.md` and `GLOSSARY.md`.
- Prefer “system” (automation capability) and “workflow” (ordered steps). Avoid mixing with “engine” or “pipeline” unless defined.
