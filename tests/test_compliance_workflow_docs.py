import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "cross-repo-compliance.yml"
DOC_PATH = REPO_ROOT / "docs" / "cross-repo-compliance.md"


def test_cross_repo_compliance_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists(), "cross-repo compliance workflow is missing"


def test_docs_reference_compliance_workflow() -> None:
    content = DOC_PATH.read_text()
    assert "cross-repo-compliance.yml" in content
    assert "Automated Compliance Monitoring" in content


def test_workflow_referenced_config_exists() -> None:
    workflow_text = WORKFLOW_PATH.read_text()
    match = re.search(r"--config\s+([^\s\\]+)", workflow_text)
    assert match, "Workflow must specify a --config path"
    config_path = REPO_ROOT / match.group(1)
    assert config_path.exists(), f"Config path referenced in workflow does not exist: {config_path}"
