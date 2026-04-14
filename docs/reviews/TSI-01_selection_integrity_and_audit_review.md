# TSI-01 Selection Integrity + Trust-Gap Audit Review

## 1. Intent
Implement fail-closed hardening so PR trust cannot pass on pytest execution evidence alone by requiring governed pytest selection integrity evidence, and add a deterministic read-only audit path for recent historical trust gaps.

## 2. Files added
- `docs/review-actions/PLAN-TSI-01-2026-04-14.md`
- `docs/governance/pytest_pr_selection_integrity_policy.json`
- `contracts/schemas/pytest_selection_integrity_result.schema.json`
- `contracts/examples/pytest_selection_integrity_result.json`
- `contracts/schemas/pytest_trust_gap_audit_result.schema.json`
- `contracts/examples/pytest_trust_gap_audit_result.json`
- `spectrum_systems/modules/runtime/pytest_selection_integrity.py`
- `spectrum_systems/modules/runtime/pytest_trust_gap_audit.py`
- `scripts/run_pytest_trust_gap_audit.py`
- `tests/test_pytest_selection_integrity.py`
- `tests/test_pytest_trust_gap_audit.py`

## 3. Files modified
- `scripts/run_contract_preflight.py`
- `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py`
- `spectrum_systems/modules/runtime/preflight_failure_normalizer.py`
- `contracts/schemas/contract_preflight_result_artifact.schema.json`
- `contracts/examples/contract_preflight_result_artifact.json`
- `contracts/examples/contract_preflight_result_artifact.example.json`
- `contracts/schemas/preflight_block_diagnosis_record.schema.json`
- `contracts/schemas/failure_repair_candidate_artifact.schema.json`
- `contracts/examples/preflight_block_diagnosis_record.json`
- `contracts/standards-manifest.json`
- `.github/workflows/artifact-boundary.yml`
- `.github/workflows/pr-autofix-contract-preflight.yml`
- `docs/governance/test_inventory_integrity.md`
- `tests/test_contract_preflight.py`
- `tests/test_github_pr_autofix_contract_preflight.py`
- `tests/test_test_inventory_integrity.py`
- `tests/test_pqx_slice_runner.py`
- `tests/test_contracts.py`

## 4. New artifacts/contracts introduced
- `pytest_selection_integrity_result` (new governed artifact + schema + example)
- `pytest_trust_gap_audit_result` (new governed artifact + schema + example)
- `contract_preflight_result_artifact` v`1.4.0` additive fields:
  - `pytest_selection_integrity`
  - `pytest_selection_integrity_result_ref`

## 5. Policy decisions
- Minimum PR selection threshold is explicit and versioned in governed policy (`minimum_selection_threshold: 1`).
- Surface-to-required-test mapping is explicit and fail-closed in policy (`surface_rules`).
- Bounded equivalence is explicit and opt-in (`allow_bounded_equivalence`).
- Missing/invalid selection integrity evidence is treated as BLOCK.

## 6. Failure modes closed
- PR allow with empty pytest target selection.
- PR allow with missing required governed target coverage.
- PR allow with threshold under-selection.
- PR allow with missing/invalid selection integrity artifact.
- PR allow with filtering-detected target collapse.
- Autofix false-success when rerun lacks valid execution + valid selection integrity evidence.

## 7. Remaining risks
- Historical runs without artifacts remain uncertain; audit explicitly classifies as suspect/unknown rather than fabricating trust.
- Governance policy drift can re-open gaps if mappings are not updated with new governed surfaces.

## 8. Tests added/updated
- Added `tests/test_pytest_selection_integrity.py`.
- Added `tests/test_pytest_trust_gap_audit.py`.
- Updated preflight tests for selection-integrity BLOCK and artifact emission paths.
- Updated autofix tests for new selection-integrity failure classes and bounded repair behavior.
- Updated contract tests and pqx slice runner fixtures for new preflight artifact schema requirements.

## 9. Validation commands run
1. `python scripts/run_contract_preflight.py --help`
2. `python -m pytest -q tests/test_contract_preflight.py`
3. `python -m pytest -q tests/test_github_pr_autofix_contract_preflight.py`
4. `python -m pytest -q tests/test_test_inventory_integrity.py`
5. `python -m pytest -q tests/`
6. `python scripts/run_contract_enforcement.py`

## 10. Exact results
- `python scripts/run_contract_preflight.py --help` exited `0`.
- `python -m pytest -q tests/test_contract_preflight.py` passed (`71 passed`).
- `python -m pytest -q tests/test_github_pr_autofix_contract_preflight.py` passed (`27 passed`).
- `python -m pytest -q tests/test_test_inventory_integrity.py` passed (`9 passed`).
- `python -m pytest -q tests/` passed (`6655 passed, 1 skipped`).
- `python scripts/run_contract_enforcement.py` passed (`failures=0 warnings=0 not_yet_enforceable=0`).

## 11. Follow-on recommendations
- Add a CI job that runs `scripts/run_pytest_trust_gap_audit.py` on a bounded rolling window and publishes suspect trend history.
- Add a policy-change checklist requiring same-change updates to `pytest_pr_selection_integrity_policy.json` for new governed runtime surfaces.
