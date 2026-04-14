# AUD-02 Required Check Alignment and Trust Gap Audit

## Prompt type
REVIEW

## 1. Intent
Implement a surgical, deterministic audit layer that verifies the authoritative PR-visible pytest required check target (`PR / pytest`) and backtests recent local preflight artifacts for historical trust-gap exposure without weakening existing preflight trust controls.

## 2. What was audited
- Workflow authority surface: `.github/workflows/artifact-boundary.yml` (`pytest-pr`, display `PR / pytest`).
- Governed required-check policy declaration: `docs/governance/required_pr_checks.json`.
- Optional local required-check evidence surfaces (if present):
  - `.github/branch_protection_rules.json`
  - `.github/required_status_checks.json`
- Optional live GitHub evidence payload (operator-supplied path).
- Recent preflight artifacts discovered under bounded local roots:
  - `outputs/**/contract_preflight_result_artifact.json`
  - `artifacts/**/contract_preflight_result_artifact.json`
  - `data/**/contract_preflight_result_artifact.json`

## 3. Expected required status check
- Workflow: `artifact-boundary`
- Authoritative job id: `pytest-pr`
- Authoritative display name: `PR / pytest`
- Required status check name: `PR / pytest`

## 4. Whether local repo policy aligns
- Local governed declaration aligns with workflow authority (`docs/governance/required_pr_checks.json`).
- Audit semantics fail closed on drift:
  - policy/workflow/job/display mismatch => `BLOCK`
  - local required-check evidence referencing obsolete `contract-preflight` => `BLOCK`

## 5. Whether live GitHub protection could be proven
- Current run outcome: **could not be proven from repo-local evidence alone**.
- Audit emits `live_github_alignment_status=unknown` and `final_decision=WARN` unless explicit live evidence is supplied and aligned.
- Unknown is never treated as pass-equivalent.

## 6. Backtest window and evidence sources
- Window: bounded local scan roots (`outputs`, `artifacts`, `data`) with deterministic max artifact cap.
- Primary trust evidence: governed preflight artifacts and canonical refs:
  - `pytest_execution`
  - `pytest_execution_record_ref`
  - `pytest_selection_integrity`
  - `pytest_selection_integrity_result_ref`
- Raw logs are not primary trust evidence.

## 7. Suspect runs / findings
- Classification categories implemented:
  - `trustworthy`
  - `suspect_missing_pytest_execution_evidence`
  - `suspect_missing_selection_integrity_evidence`
  - `suspect_noncanonical_ref_acceptance`
  - `suspect_warn_pass_equivalence`
  - `suspect_degraded_ref_resolution`
  - `insufficient_evidence_to_determine`
- Current local sample scan result (this run):
  - evaluated runs: `0`
  - suspect runs: `0`
  - final decision: `PASS`
- Deterministic output artifact path:
  - `outputs/pytest_trust_gap_audit/pytest_trust_gap_backtest_result.json`

## 8. Confidence limits
- Backtest is intentionally bounded to local artifacts available in-repo.
- Missing historical artifacts are classified as explicit uncertainty (`insufficient_evidence_to_determine`), not inferred as clean.
- Live branch-protection configuration remains operator-owned unless provided as explicit evidence payload.

## 9. Required operator actions
1. Verify GitHub branch protection for target branches requires status check `PR / pytest`.
2. Remove obsolete required checks (e.g., `contract-preflight`) if still configured in GitHub settings.
3. Optionally export branch-protection required-check evidence as JSON and rerun:
   - `python scripts/run_required_check_alignment_audit.py --live-github-evidence-path <path-to-json>`

## 10. Final verdict
- **Local governance and workflow surfaces are aligned.**
- **Live GitHub branch-protection alignment is currently unknown without operator-supplied evidence.**
- **Trust-gap backtest path is implemented with explicit suspect/uncertainty classification and deterministic artifact output.**

---

## Mandatory delivery contract report

### 1. Intent
Deliver AUD-02 required-check alignment and trust-gap backtest enforcement with deterministic governed artifacts and explicit unknown-state handling.

### 2. Files added
- `docs/review-actions/PLAN-AUD-02-2026-04-14.md`
- `docs/governance/required_pr_checks.json`
- `scripts/run_required_check_alignment_audit.py`
- `spectrum_systems/modules/runtime/required_check_alignment_audit.py`
- `contracts/schemas/required_check_alignment_audit_result.schema.json`
- `contracts/examples/required_check_alignment_audit_result.json`
- `contracts/schemas/pytest_trust_gap_backtest_result.schema.json`
- `contracts/examples/pytest_trust_gap_backtest_result.json`
- `tests/test_required_check_alignment_audit.py`

### 3. Files modified
- `scripts/run_pytest_trust_gap_audit.py`
- `spectrum_systems/modules/runtime/pytest_trust_gap_audit.py`
- `tests/test_pytest_trust_gap_audit.py`
- `tests/test_contracts.py`
- `contracts/examples/pytest_execution_record.json`
- `contracts/standards-manifest.json`

### 4. New artifacts/contracts introduced
- `required_check_alignment_audit_result` (schema + example + runtime + CLI)
- `pytest_trust_gap_backtest_result` (schema + example + runtime + CLI output)
- Governed policy declaration for required PR check target: `docs/governance/required_pr_checks.json`

### 5. Policy decisions
- Canonical required status check is `PR / pytest`.
- PASS requires positive proof of live alignment.
- Unknown live alignment remains WARN + operator action required.
- Drift/contradiction is BLOCK.

### 6. Audit logic implemented
- Workflow authority extraction from `.github/workflows/artifact-boundary.yml`.
- Policy/workflow/job/display consistency verification.
- Optional local and live required-check evidence comparison.
- Deterministic final decisions: `PASS` / `WARN` / `BLOCK`.

### 7. Backtest logic implemented
- Bounded deterministic scan for local preflight artifacts.
- Artifact-first classification using governed evidence refs.
- Explicit suspect classes for missing execution, missing selection integrity, noncanonical refs, WARN/pass equivalence, degraded resolution, and insufficient evidence.
- Deterministic summary counts and final decision.

### 8. Tests added/updated
- Added: `tests/test_required_check_alignment_audit.py`
- Updated: `tests/test_pytest_trust_gap_audit.py`
- Updated contract example validation coverage in `tests/test_contracts.py`

### 9. Validation commands run
1. `python -m pytest -q tests/test_artifact_boundary_workflow_pytest_enforcement.py`
2. `python -m pytest -q tests/test_contract_preflight.py`
3. `python -m pytest -q tests/test_pytest_selection_integrity.py`
4. `python -m pytest -q tests/test_required_check_alignment_audit.py`
5. `python -m pytest -q tests/test_pytest_trust_gap_audit.py`
6. `python -m pytest -q tests/test_contracts.py`
7. `python scripts/run_contract_enforcement.py`
8. `python scripts/run_required_check_alignment_audit.py`
9. `python scripts/run_pytest_trust_gap_audit.py`

### 10. Exact results
- All required pytest suites passed.
- `run_contract_enforcement.py` passed with `failures=0 warnings=0 not_yet_enforceable=0`.
- `run_required_check_alignment_audit.py` produced:
  - `outputs/required_check_alignment_audit/required_check_alignment_audit_result.json`
  - `final_decision=WARN` (live alignment unknown)
- `run_pytest_trust_gap_audit.py` produced:
  - `outputs/pytest_trust_gap_audit/pytest_trust_gap_backtest_result.json`
  - `evaluated_runs=0`, `suspect_runs=0`, `final_decision=PASS`

### 11. Operator actions still required
- Confirm GitHub branch protection required check includes `PR / pytest`.
- Remove obsolete required checks if configured.
- Provide live branch-protection evidence JSON for PASS-grade proof when needed.

### 12. Remaining risks
- Repo-local audits cannot independently prove live GitHub settings without explicit exported evidence.
- Historical backtest confidence depends on retention/completeness of local governed artifacts.
