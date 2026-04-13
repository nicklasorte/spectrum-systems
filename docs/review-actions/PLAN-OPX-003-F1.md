# PLAN — OPX-003-F1 Artifact Class Taxonomy Fix — 2026-04-13

## Prompt Type
BUILD

## Intent
Repair OPX-003 artifact class taxonomy drift by restoring canonical standards-manifest classes, centralizing artifact-class authority in one source, and hardening fail-fast validation paths for manifest and dependency graph generation.

## Target files
- `contracts/standards-manifest.json` (MODIFY)
- `spectrum_systems/contracts/artifact_class_taxonomy.py` (CREATE)
- `spectrum_systems/governance/manifest_validator.py` (MODIFY)
- `scripts/build_dependency_graph.py` (MODIFY)
- `tests/test_artifact_classification.py` (MODIFY)
- `tests/test_manifest_completeness.py` (MODIFY)
- `tests/test_dependency_graph.py` (MODIFY)
- `tests/test_artifact_class_taxonomy_alignment.py` (CREATE)
- `docs/reviews/2026-04-13_opx_003_f1_artifact_class_taxonomy_fix.md` (CREATE)

## Failure modes being closed
- Non-canonical artifact class values in standards manifest (`control`) bypassing local assumptions.
- Duplicated allowed-class enums drifting between tests, validators, and dependency graph schema.
- Dependency graph generation silently coercing invalid classes instead of failing closed.
- Lack of preflight checks ensuring dependency graph schema enum matches canonical taxonomy.
