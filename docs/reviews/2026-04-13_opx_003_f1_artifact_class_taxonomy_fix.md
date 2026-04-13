# OPX-003-F1 Artifact Class Taxonomy Fix — 2026-04-13

## 1. Exact failure
- `tests/test_artifact_classification.py::ArtifactClassificationTests::test_manifest_artifact_classes_are_allowed` failed because OPX-003 entries used `artifact_class="control"`, which is not part of canonical classes.
- `tests/test_dependency_graph.py::test_dependency_graph_pipeline` failed because dependency-graph schema enforces canonical class enum and rejected `control` from standards manifest.

## 2. Root cause
- Artifact class taxonomy authority drifted across multiple surfaces:
  - standards manifest entries were authored with non-canonical class value (`control`)
  - test/constants and dependency graph schema expected canonical set
  - `manifest_validator` had an outdated, non-canonical enum set
  - dependency graph builder silently coerced invalid classes via inference instead of failing closed
- Net root cause: duplicated taxonomy definitions with no enforced canonical runtime source.

## 3. Canonical classification decision taken
- Reclassified OPX-003 artifacts (`operator_action_request_artifact`, `operator_action_resolution_artifact`, `operator_evidence_bundle_artifact`, `recommendation_comparison_artifact`, `reuse_record_artifact`) to canonical `governance` because they are governed control-plane/operator-decision artifacts.

## 4. Files changed
- `contracts/standards-manifest.json`
- `spectrum_systems/contracts/artifact_class_taxonomy.py`
- `spectrum_systems/governance/manifest_validator.py`
- `scripts/build_dependency_graph.py`
- `tests/test_artifact_classification.py`
- `tests/test_manifest_completeness.py`
- `tests/test_artifact_class_taxonomy_alignment.py`
- `docs/review-actions/PLAN-OPX-003-F1.md`
- `docs/reviews/2026-04-13_opx_003_f1_artifact_class_taxonomy_fix.md`
- regenerated graph/report artifacts:
  - `ecosystem/dependency-graph.json`
  - `artifacts/dependency-graph-summary.md`
  - `artifacts/dependency-graph.mmd`
  - `governance/reports/contract-dependency-graph.json`
  - `docs/governance-reports/contract-enforcement-report.md`

## 5. Automatic prevention added
- Added canonical loader `load_allowed_artifact_classes()` sourced from `contracts/artifact-class-registry.json`.
- Wired `manifest_validator` to canonical taxonomy loader.
- Hardened `build_dependency_graph.py` to fail fast when:
  - standards-manifest contains non-canonical classes
  - graph artifact classes are non-canonical
  - dependency graph schema enum drifts from canonical taxonomy
- Added alignment tests ensuring standards manifest + dependency graph schema stay synchronized with canonical taxonomy.

## 6. Tests/validation run and results
- `pytest tests/test_artifact_classification.py -q` ✅
- `pytest tests/test_dependency_graph.py -q` ✅
- `pytest tests/test_contract_bootstrap.py -q` ✅
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q` ✅
- `pytest tests/test_manifest_completeness.py tests/test_artifact_class_taxonomy_alignment.py -q` ✅

## 7. Remaining seams
- Dependency graph schema still stores enum values statically in JSON; drift is now fail-fast detected by tests + script preflight, but fully generated-schema synchronization could be added later if desired.

## Terminal summary
- root cause fixed: yes (taxonomy drift + fail-open coercion removed)
- files changed: standards manifest, canonical taxonomy module, validator, dependency graph builder, and alignment tests
- tests run: 5 command groups, all passing
- pass/fail: PASS
- recurrence prevention: single taxonomy source + validator + script fail-fast + schema alignment tests
- follow-up seams: optional future automation to generate dependency graph schema enum from canonical taxonomy source
