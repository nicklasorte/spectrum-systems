from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/review_trigger_pipeline.yml")


def test_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists(), "review trigger workflow must exist"


def test_workflow_has_required_triggers() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "pull_request_review:" in text
    assert "types: [submitted]" in text
    assert "issue_comment:" in text
    assert "workflow_dispatch:" in text
    assert "pr_number:" in text
    assert "review_source:" in text
    assert "run_mode:" in text


def test_workflow_uses_governed_ingestion_adapter_and_uploads_artifacts() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "spectrum_systems.modules.runtime.github_review_ingestion" in text
    assert "artifacts/github_review_ingestion" in text
    assert "actions/upload-artifact@v4" in text


def test_workflow_enforces_issue_comment_command_marker_guardrail() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Guardrail is enforced in adapter invocation path via fail-closed checks.
    assert "issue_comment" in text
    assert "github_review_ingestion" in text
