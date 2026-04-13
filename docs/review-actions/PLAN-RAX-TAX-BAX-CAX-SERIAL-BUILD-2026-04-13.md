# PLAN — RAX TAX/BAX/CAX Serial Build (2026-04-13)

## Prompt type
`BUILD`

## Scope
Register and implement TAX, BAX, and CAX as governed runtime authorities without changing canonical ownership boundaries (CDE remains final closure-state owner; SEL remains enforcement owner).

## Serial execution phases
1. **Phase 1: Registry + contract foundation**
   - Update canonical registry surfaces (`docs/architecture/system_registry.md`, `contracts/examples/system_registry_artifact.json`).
   - Add TAX/BAX/CAX schemas + examples.
   - Update `contracts/standards-manifest.json` with version bump and contract entries.
   - Write `docs/reviews/tax_bax_cax_phase1_registry_and_contracts.md`.
2. **Phase 2: TAX runtime authority**
   - Add `spectrum_systems/modules/runtime/tax.py` with fail-closed termination decisioning.
   - Wire helper usage into governed seams where safe.
   - Write `docs/reviews/tax_phase2_termination_authority.md`.
3. **Phase 3: BAX runtime authority**
   - Add `spectrum_systems/modules/runtime/bax.py` with cost/quality/risk status and decision artifact emission.
   - Write `docs/reviews/bax_phase3_budget_authority.md`.
4. **Phase 4: CAX composition authority**
   - Add `spectrum_systems/modules/runtime/cax.py` with deterministic precedence and CDE input bundle preparation.
   - Wire CAX output as pre-CDE bounded input in runtime governance path.
   - Write `docs/reviews/cax_phase4_control_arbitration.md`.
5. **Phase 5: Hard gates + certification + A2A guard**
   - Extend done certification and enforcement checks to require TAX/BAX/CAX lineage in governed promotion paths.
   - Add fail-closed downstream artifact consumption guard.
   - Write `docs/reviews/phase5_hard_gates_certification_a2a_guard.md`.
6. **Phase 6: Tests + red-team + operator surface updates**
   - Add deterministic tests for TAX/BAX/CAX behavior, precedence, replay stability, certification gating, and A2A guard.
   - Write `docs/reviews/phase6_tests_redteam_operator_surfaces.md`.

## Checkpoints
- Produce required phase review artifacts after each phase.
- Run contract and targeted runtime tests before completion.
- Produce final red-team artifact and serial delivery report.
