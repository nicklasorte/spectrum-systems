# System Registry Authority Surface Alignment Review

Date: 2026-04-13

## Scope
Markdown authority-alignment pass to ensure one clear ownership authority surface:
- `docs/architecture/system_registry.md` (canonical authority)

## Files updated
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

Additional process artifact:
- `docs/review-actions/PLAN-SYSTEM-REGISTRY-AUTHORITY-ALIGNMENT-2026-04-13.md`

## Files intentionally left unchanged
Within the requested list, no files were left unchanged.

## Authority-surface changes made
1. Replaced authority-like ownership duplication in operator guidance docs (`README.md`, `AGENTS.md`, `CODEX.md`, `CLAUDE.md`) with concise summaries and explicit canonical deferral to `docs/architecture/system_registry.md`.
2. Converted `docs/system-registry.md` from authoritative wording to an ecosystem companion summary that explicitly defers ownership authority.
3. Converted `docs/systems-registry.md` into a compatibility companion stub for legacy links.
4. Updated ecosystem/map docs to clarify they are companion/operational surfaces, not ownership authorities.

## Docs reduced from authority-like to companion status
- `docs/system-registry.md` → ecosystem companion summary (derived).
- `docs/systems-registry.md` → compatibility companion stub.
- `docs/ecosystem-map.md` → companion overview with explicit ownership-authority deferral.

## Stale path references fixed
- Updated registry authority references to explicitly use `docs/architecture/system_registry.md`.
- Updated/clarified references that previously implied `docs/system-registry.md` or `docs/systems-registry.md` were authoritative.
- Added explicit bridge guidance where legacy links still target companion docs.

## Duplicate ownership definitions removed or synced
- Removed hard-coded ownership tables/sets from non-canonical guidance surfaces where they could drift.
- Replaced with concise summaries plus canonical pointer to avoid parallel constitutions.

## Unresolved ambiguity
- None identified in the updated authority surfaces.
