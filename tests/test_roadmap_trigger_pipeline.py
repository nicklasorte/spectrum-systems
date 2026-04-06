from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path('.github/workflows/review_trigger_pipeline.yml')


def test_workflow_supports_roadmap_2step_command() -> None:
    text = WORKFLOW_PATH.read_text(encoding='utf-8')

    assert '/roadmap-2step' in text
    assert 'issue_comment trigger allowed only for pull request threads' in text
    assert 'issue_comment trigger requires approved command marker' in text


def test_workflow_continues_using_governed_ingestion_adapter() -> None:
    text = WORKFLOW_PATH.read_text(encoding='utf-8')

    assert 'spectrum_systems.modules.runtime.github_review_ingestion' in text
    assert 'github_review_handoff_artifact' in text
