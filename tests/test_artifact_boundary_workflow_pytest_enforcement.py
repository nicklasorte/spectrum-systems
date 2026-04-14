from pathlib import Path


ARTIFACT_BOUNDARY_WORKFLOW = Path('.github/workflows/artifact-boundary.yml')
AUTOFIX_WORKFLOW = Path('.github/workflows/pr-autofix-contract-preflight.yml')


def test_artifact_boundary_workflow_uses_contract_preflight_on_pull_request() -> None:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    assert 'pull_request:' in text
    assert 'python scripts/run_contract_preflight.py' in text


def test_artifact_boundary_workflow_fail_closes_on_missing_pytest_execution_record() -> None:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest_execution_record_ref' in text
    assert 'missing pytest_execution_record_ref' in text
    assert 'executed=false' in text
    assert 'empty selected_targets' in text


def test_autofix_workflow_enforces_pytest_execution_record_for_allow_warn() -> None:
    text = AUTOFIX_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest_execution_record_ref' in text
    assert 'allow decision with executed=false' in text
    assert 'allow decision with empty selected_targets' in text
