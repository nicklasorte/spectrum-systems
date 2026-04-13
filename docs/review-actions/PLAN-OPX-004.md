# PLAN-OPX-004 (BUILD)

## Intent
Implement OPX-79 through OPX-110 as deterministic runtime execution code, governed artifacts, and tests without introducing new subsystem ownership.

## Steps
1. Inspect existing OPX runtime, tests, and contract publication format for repo-native extension points.
2. Implement OPX-004 durability/self-correction logic in `spectrum_systems/opx/runtime.py` with explicit owner-safe artifacts and bounded behavior.
3. Publish a contract schema and manifest entry for OPX durability cycle artifacts.
4. Add deterministic tests covering mandatory OPX-004 slices and non-duplication constraints.
5. Run required tests (including contract tests for schema changes), fix regressions, and produce implementation review artifact.
6. Commit changes and create PR message.
