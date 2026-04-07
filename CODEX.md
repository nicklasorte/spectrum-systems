# CODEX.md

## Purpose
Role-specific instructions for Codex in `spectrum-systems`.

This repository is a **governed runtime control plane**. Codex modifies governance artifacts, contracts, schemas, and documentation. It does not implement downstream runtime engine code.

## Canonical sources
Before execution, align with:
1. `README.md` (system identity and operating model)
2. `docs/architecture/system_registry.md` (canonical system roles and ownership)

If another file conflicts, resolve toward these sources and record the conflict in the change summary.

## Codex role
Codex is the implementation agent for repository updates.
- Execute approved scope changes deterministically.
- Keep instructions explicit and minimal.
- Avoid undocumented behavior changes.
- Do not redefine subsystem roles.

## Required runtime model
All modifications must preserve:
1. **Artifact-first execution**
2. **Fail-closed behavior**
3. **Promotion requires certification**

## System role map (reference)
Treat `RIL`, `CDE`, `TLC`, `PQX`, `FRE`, `SEL`, and `PRG` as authoritative role names and ownership boundaries from `docs/architecture/system_registry.md`.

## Execution rules
- One prompt has one primary transformation type.
- Multi-file governance changes require a written plan before implementation.
- Keep reference depth shallow (max one level) in high-impact docs.
- Remove duplicate logic; keep one canonical definition per concept.

## Terminology normalization
Use these terms consistently in modified docs:
- **execution**
- **artifact**
- **failure**
- **retrieve**

## Cross-links
- `README.md`
- `docs/architecture/system_registry.md`
