# Three-Letter Ownership Policy (Canonical Governed Runtime)

## Purpose
Enforce explicit 3-letter ownership over governed runtime behavior while allowing support-only code.

## Policy
1. Every governed behavior must map to exactly one owning 3-letter system.
2. Support-only code is allowed, but support-only code must not emit authority-bearing artifacts or decisions.
3. Shared utilities may assist owners but do not inherit authority.
4. New governed runtime code must declare one of:
   - explicit owning 3-letter system, or
   - explicit `support_only` / non-authority classification.
5. Docs/tests/examples/templates are non-authority by default unless they execute governed runtime behavior.

## Canonical sources
- Runtime ownership authority: `docs/architecture/system_registry.md`.
- Runtime source of truth artifact: `contracts/examples/system_registry_artifact.json` (rebuilt through `scripts/build_system_registry_artifact.py`).
- Governed path admission map: `docs/governance/governed_runtime_ownership_map.json`.

## Admission enforcement
Use `scripts/validate_governed_runtime_ownership.py` in CI and local preflight to fail closed on unclassified governed runtime additions.
