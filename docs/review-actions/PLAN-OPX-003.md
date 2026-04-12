# PLAN — OPX-003 Roadmap Runtime Build — 2026-04-12

## Prompt Type
BUILD

## Intent
Implement a deterministic, artifact-first OPX-003 runtime that serially executes slices OPX-29 through OPX-48 with fail-closed governance boundaries, operator-action routing, evidence bundles, FAQ hardening, module-template reuse, compatibility/conflict/trust/burden artifacts, champion/challenger controls, maintain-stage output, simulation promotion, red-team packs/fix waves, and governed semantic cache behavior.

## Target files
- `spectrum_systems/opx/runtime.py` (MODIFY)
- `contracts/schemas/operator_action_request_artifact.schema.json` (CREATE)
- `contracts/schemas/operator_action_resolution_artifact.schema.json` (CREATE)
- `contracts/schemas/operator_evidence_bundle_artifact.schema.json` (CREATE)
- `contracts/schemas/recommendation_comparison_artifact.schema.json` (CREATE)
- `contracts/schemas/reuse_record_artifact.schema.json` (CREATE)
- `contracts/examples/operator_action_request_artifact.json` (CREATE)
- `contracts/examples/operator_action_resolution_artifact.json` (CREATE)
- `contracts/examples/operator_evidence_bundle_artifact.json` (CREATE)
- `contracts/examples/recommendation_comparison_artifact.json` (CREATE)
- `contracts/examples/reuse_record_artifact.json` (CREATE)
- `contracts/standards-manifest.json` (MODIFY)
- `tests/test_opx_003_full_build.py` (CREATE)
- `docs/reviews/2026-04-12_opx_003_implementation_review.md` (CREATE)

## Contracts touched
- New contracts:
  - `operator_action_request_artifact` v1.0.0
  - `operator_action_resolution_artifact` v1.0.0
  - `operator_evidence_bundle_artifact` v1.0.0
  - `recommendation_comparison_artifact` v1.0.0
  - `reuse_record_artifact` v1.0.0
- Standards manifest will be incremented and updated with schema + example paths.

## Tests to add/update
- Add `tests/test_opx_003_full_build.py` covering mandatory OPX-003 controls and deterministic output.
- Run changed-scope tests:
  - `pytest tests/test_opx_003_full_build.py tests/test_opx_002_operator_grade_roadmap.py tests/test_opx_001_full_roadmap.py`
  - `pytest tests/test_contracts.py tests/test_contract_enforcement.py`

## Failure modes being closed
- Operator action direct mutation bypassing authority lineage.
- Non-deterministic or untraceable operator evidence bundle generation.
- FAQ override/replay/certification discipline drift.
- Missing deterministic conversion from feedback to eval/dataset artifacts.
- Template reuse drift across module families.
- Hidden compatibility breakage and policy/judgment contradictions.
- Fail-open red-team/findings/fix-wave handling.
- Unsafe semantic cache reuse without strict governance match.
