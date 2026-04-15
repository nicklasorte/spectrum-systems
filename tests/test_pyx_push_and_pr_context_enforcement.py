from __future__ import annotations

import json
from pathlib import Path


ARTIFACT_BOUNDARY_WORKFLOW = Path(".github/workflows/artifact-boundary.yml")
PR_PYTEST_WORKFLOW = Path(".github/workflows/pr-pytest.yml")
REQUIRED_CHECK_POLICY = Path("docs/governance/required_pr_checks.json")


def test_push_and_pull_request_triggers_are_explicit_and_separated() -> None:
    artifact_text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding="utf-8")
    pr_text = PR_PYTEST_WORKFLOW.read_text(encoding="utf-8")
    assert "on:" in artifact_text
    assert "push:" in artifact_text
    assert "pull_request:" in artifact_text
    assert "on:" in pr_text
    assert "pull_request:" in pr_text
    assert "push:" not in pr_text


def test_pr_visible_check_surface_remains_pr_slash_pytest() -> None:
    policy = json.loads(REQUIRED_CHECK_POLICY.read_text(encoding="utf-8"))
    pr_text = PR_PYTEST_WORKFLOW.read_text(encoding="utf-8")
    assert policy["workflow"] == "PR"
    assert policy["authoritative_job_id"] == "pytest"
    assert policy["authoritative_display_name"] == "pytest"
    assert policy["required_status_check_name"] == "PR / pytest"
    assert "name: PR" in pr_text
    assert "pytest:" in pr_text
    assert "name: pytest" in pr_text


def test_push_preflight_and_pr_preflight_use_governed_contract_entrypoint() -> None:
    artifact_text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding="utf-8")
    pr_text = PR_PYTEST_WORKFLOW.read_text(encoding="utf-8")
    assert "Run authoritative governed preflight gate (push)" in artifact_text
    assert "python scripts/run_contract_preflight.py" in artifact_text
    assert "--execution-context pqx_governed" in artifact_text
    assert "Run governed pytest preflight gate" in pr_text
    assert "python scripts/run_contract_preflight.py" in pr_text
