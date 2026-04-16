# PLAN-FIX-TRN-02-REG-01-2026-04-16

- Prompt type: BUILD
- Scope: Resolve SRG overlaps introduced in TRN-02 by restoring owner boundaries.

## Root focus
- Keep transcript hardening in transcript-domain processing only.
- Remove any protected-authority semantics from module/schema/docs in scope.
- Verify SRG pass with touched-file set.

## Execution sequence
1. Inspect canonical owner surfaces (`docs/architecture/system_registry.md`, guard policy, owner modules).
2. Refactor transcript hardening code + schema to remove protected decisions.
3. Update tests with guard-regression coverage.
4. Update delivery docs to state bounded ownership.
5. Run SRG and required tests.
