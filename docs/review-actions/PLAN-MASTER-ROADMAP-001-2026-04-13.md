# PLAN — MASTER-ROADMAP-001 (BUILD)

## Scope
Implement repo-native coverage for the remaining advanced systems not yet landed in runtime/contracts:
CAL, POL, AIL, SCH, DEP, RCA, QOS, and SIMX, plus registry/validation wiring and deterministic tests.

## Steps
1. Update `docs/architecture/system_registry.md` with canonical definitions and system map entries for CAL/POL/AIL/SCH/DEP/RCA/QOS/SIMX.
2. Add contract schemas and examples for each new system artifact family.
3. Register all new artifact types in `contracts/standards-manifest.json`.
4. Add deterministic runtime modules in `spectrum_systems/modules/runtime/` for each new system:
   - eval artifact
   - readiness artifact (candidate-only assertions)
   - replay validation
   - effectiveness signal
   - red-team round output
5. Extend registry boundary validator/tests to require and validate the new systems.
6. Add a runtime/system integration test suite covering authority-boundary behavior for all newly added systems.
7. Run required contract + enforcement + targeted tests and fix regressions.
