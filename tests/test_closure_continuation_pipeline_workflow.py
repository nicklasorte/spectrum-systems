from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/closure_continuation_pipeline.yml")


def test_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists(), "closure continuation workflow must exist"


def test_workflow_has_required_triggers() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_run:" in text
    assert "workflows: [\"review-trigger-pipeline\"]" in text
    assert "types: [completed]" in text
    assert "workflow_dispatch:" in text


def test_workflow_chains_from_review_trigger_and_downloads_artifacts() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "dawidd6/action-download-artifact@v6" in text
    assert "review-trigger-pipeline-artifacts" in text


def test_workflow_invokes_continuation_adapter_and_publishes_summary() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "spectrum_systems.modules.runtime.github_closure_continuation" in text
    assert "artifacts/github_closure_continuation" in text
    assert "CDE decision" in text
    assert "Final terminal state" in text


def test_workflow_includes_guardrail_failure_points() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "missing ingestion_result.json" in text
    assert "if_no_artifact_found: fail" in text
