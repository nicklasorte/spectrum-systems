# Plan — System Registry Authority Surface Alignment — 2026-04-13

## Objective
Align canonical markdown authority surfaces to the updated canonical registry in `docs/architecture/system_registry.md`, remove competing authority language, and reduce duplicate ownership definitions.

## Scope
- Update only markdown authority/navigation surfaces requested in the task.
- Keep architecture intent unchanged.
- Do not modify JSON registries/schemas.

## Files
- `README.md`
- `AGENTS.md`
- `CODEX.md`
- `CLAUDE.md`
- `REPO_MAP.md`
- `SYSTEMS.md`
- `docs/system-map.md`
- `docs/system-registry.md`
- `docs/systems-registry.md`
- `docs/ecosystem-map.md`
- `docs/ecosystem-architecture.md`
- `docs/reviews/system_registry_authority_surface_alignment_review.md` (new)

## Execution Steps
1. Read `docs/architecture/system_registry.md` and treat it as authoritative.
2. Audit listed files for stale acronym sets, stale authority claims, and stale paths.
3. Replace duplicate ownership tables with concise summaries plus canonical pointer where appropriate.
4. Convert `docs/system-registry.md` and `docs/systems-registry.md` to explicit companion/compatibility docs.
5. Re-scan targeted files for stale references and conflicting canonical language.
6. Add a review note documenting updates, unchanged files, authority reductions, path fixes, and ambiguities.
