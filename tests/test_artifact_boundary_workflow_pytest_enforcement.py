from pathlib import Path


ARTIFACT_BOUNDARY_WORKFLOW = Path('.github/workflows/artifact-boundary.yml')
PR_PYTEST_WORKFLOW = Path('.github/workflows/pr-pytest.yml')
AUTOFIX_WORKFLOW = Path('.github/workflows/pr-autofix-contract-preflight.yml')


def test_pr_pytest_workflow_uses_contract_preflight_on_pull_request() -> None:
    text = PR_PYTEST_WORKFLOW.read_text(encoding='utf-8')
    assert 'pull_request:' in text
    assert 'python scripts/run_contract_preflight.py' in text


def test_pr_pytest_workflow_defines_explicit_surface_name() -> None:
    text = PR_PYTEST_WORKFLOW.read_text(encoding='utf-8')
    assert 'name: PR' in text
    assert 'pytest:' in text
    assert 'name: pytest' in text
    assert 'Run governed pytest preflight gate' in text


def test_artifact_boundary_redundant_pytest_job_no_longer_depends_on_preflight_job() -> None:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    assert '- pytest-pr' not in text
    assert '- contract-preflight' not in text
    assert '- governed-contract-preflight' not in text


def test_artifact_boundary_restores_authoritative_governed_preflight() -> None:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    assert 'governed-contract-preflight:' in text
    assert "github.event_name == 'push'" in text
    assert "github.event_name == 'pull_request'" in text
    assert 'Run authoritative governed preflight gate' in text
    assert 'python scripts/run_contract_preflight.py' in text
    assert '--execution-context pqx_governed' in text
    assert '--authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json' in text


def test_artifact_boundary_governed_preflight_is_not_replaced_by_lightweight_pytest_only() -> None:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    assert 'governed-contract-preflight:' in text
    assert 'run: pytest' in text
    assert text.index('governed-contract-preflight:') < text.index('run-pytest:')


def test_artifact_boundary_governed_preflight_checkout_depth_supports_pr_and_push_resolution() -> None:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    governed_job = text.split('governed-contract-preflight:')[1].split('\n  run-pytest:')[0]
    assert 'fetch-depth: 0' in governed_job


def test_pr_pytest_workflow_does_not_bypass_artifact_validation_on_preflight_exit_zero() -> None:
    text = PR_PYTEST_WORKFLOW.read_text(encoding='utf-8')
    assert 'if [[ "$preflight_exit" -ne 0 ]]; then' in text
    assert 'if [[ "$preflight_exit" -eq 0 ]]; then' not in text


def test_pr_pytest_workflow_fail_closes_on_missing_pytest_execution_record() -> None:
    text = PR_PYTEST_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest_execution_record_ref' in text
    assert 'missing pytest_execution_record_ref' in text
    assert 'executed=false' in text
    assert 'empty selected_targets' in text


def test_pr_pytest_workflow_fail_closes_on_missing_or_blocked_selection_integrity() -> None:
    text = PR_PYTEST_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest_selection_integrity_result_ref' in text
    assert 'missing pytest_selection_integrity_result_ref' in text
    assert 'allow decision with blocked pytest selection integrity' in text


def test_pr_pytest_workflow_enforces_canonical_refs_and_provenance() -> None:
    text = PR_PYTEST_WORKFLOW.read_text(encoding='utf-8')
    assert 'WARN is not pass-equivalent for pull_request' in text
    assert 'non-canonical pytest_execution_record_ref' in text
    assert 'missing pytest_execution_record provenance fields' in text
    assert 'non-canonical pytest_selection_integrity_result_ref' in text
    assert 'selection provenance record ref mismatch' in text


def test_autofix_workflow_enforces_pytest_execution_record_for_allow_warn() -> None:
    text = AUTOFIX_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest_execution_record_ref' in text
    assert 'WARN is not pass-equivalent for pull_request' in text
    assert 'non-canonical pytest_execution_record_ref' in text
    assert 'missing pytest_execution_record provenance fields' in text
    assert 'allow decision with executed=false' in text
    assert 'allow decision with empty selected_targets' in text


def test_autofix_workflow_enforces_selection_integrity_for_allow_warn() -> None:
    text = AUTOFIX_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest_selection_integrity_result_ref' in text
    assert 'non-canonical pytest_selection_integrity_result_ref' in text
    assert 'selection provenance record ref mismatch' in text
    assert 'selection provenance record hash mismatch' in text
    assert 'missing pytest_selection_integrity_result_ref' in text
    assert 'allow decision with blocked pytest selection integrity' in text
