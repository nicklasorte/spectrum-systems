# TST-01-25-FIX — PR #1283 authority-shape + PR gate block

## Root cause of authority-shape failure
- Newly added TST gate docs/artifacts used authority-owned language and identifiers tied to other canonical owners.
- Large generated mapping/baseline artifacts embedded many authority-owned tokens in plain text.

## Root cause of PR gate block
- Contract gate passed changed-path sets into preflight without matching wrapper-path changed-path context, causing `WRAPPER_CHANGED_PATHS_MISMATCH`.
- PR workflow and required-check policy drift triggered required producer-surface tests in contract preflight and caused block-class contract mismatch.

## Exact files changed
- `.github/workflows/pr-pytest.yml`
- `.github/workflows/nightly-deep-gate.yml`
- `scripts/run_contract_gate.py`
- `scripts/run_pr_gate.py`
- `scripts/run_runtime_test_gate.py`
- `scripts/run_governance_gate.py`
- `scripts/run_ci_drift_detector.py`
- `scripts/run_readiness_evidence_gate.py`
- `contracts/schemas/readiness_evidence_gate_result.schema.json`
- `docs/architecture/ci_gate_model.md`
- `docs/governance/ci_gate_ownership_manifest.json`
- `docs/governance/ci_runtime_budget.md`
- `docs/governance/pytest_pr_inventory_baseline.json`
- `docs/governance/pytest_pr_selection_integrity_policy.json`
- `docs/governance/required_pr_checks.json`
- `docs/governance/test_gate_mapping.json`
- `docs/reviews/TST-01_ci_test_inventory.md`
- `docs/reviews/TST-12_required_check_alignment.md`
- `docs/reviews/TST-16_gate_bypass_redteam.md`
- `docs/reviews/TST-18_parallel_gate_migration.md`
- `docs/reviews/TST-20_post_cutover_audit.md`
- `docs/reviews/TST-21_gate_parity_report.md`
- `docs/reviews/TST-25_final_delivery_report.md`
- `tests/test_ci_gate_scripts.py`
- `tests/test_ci_drift_detector.py`
- `docs/review-actions/PLAN-TST-01-25-FIX-PR1283-2026-04-28.md`

## Renamed files
- `scripts/run_certification_gate.py` → `scripts/run_readiness_evidence_gate.py`
- `contracts/schemas/certification_gate_result.schema.json` → `contracts/schemas/readiness_evidence_gate_result.schema.json`

## Exact fix applied
1. Reworded TST gate docs and artifacts to evidence/signal framing only (no ownership language).
2. Updated PR orchestrator to run all sub-gates and aggregate status while preserving fail-closed block behavior.
3. Updated runtime test gate to allow no-target fast PR mode when selection gate allows and no runtime targets are required.
4. Fixed contract gate wrapper wiring by passing identical changed-path context to both wrapper builder and preflight runner.
5. Restored PR workflow/check-policy compatibility surfaces required by existing governance tests.
6. Added readiness-evidence gate path and schema, plus drift-detector and test updates.

## Commands run
- `python scripts/run_authority_shape_preflight.py --base-ref "04de615c3469560c9aacd8742647032157530a55" --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
- `python scripts/run_pr_gate.py --base-ref "04de615c3469560c9aacd8742647032157530a55" --head-ref HEAD --output-dir outputs/pr_gate`
- `python -m pytest tests/test_ci_gate_scripts.py tests/test_ci_drift_detector.py`
- `python -m pytest tests/test_required_check_alignment_audit.py tests/test_artifact_boundary_workflow_pytest_policy_observation.py tests/test_pyx_push_and_pr_context_enforcement.py`

## Final authority-shape result
- `status: pass`
- `violation_count: 0`
- artifact: `outputs/authority_shape_preflight/authority_shape_preflight_result.json`

## Final PR gate result
- `status: allow`
- artifact: `outputs/pr_gate/pr_gate_result.json`

## Test results
- `tests/test_ci_gate_scripts.py` + `tests/test_ci_drift_detector.py`: pass
- `tests/test_required_check_alignment_audit.py` + `tests/test_artifact_boundary_workflow_pytest_policy_observation.py` + `tests/test_pyx_push_and_pr_context_enforcement.py`: pass

## Remaining risks
- Fast PR gate still depends on contract preflight execution cost for broad diffs.
- Legacy gate-name compatibility file paths still appear in preflight changed-file lists when comparing against older base commits.
