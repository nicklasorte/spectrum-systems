from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path('.github/workflows/pr-autofix-review-artifact-validation.yml')


def test_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists(), 'governed autofix workflow must exist'


def test_workflow_has_expected_workflow_run_trigger() -> None:
    text = WORKFLOW_PATH.read_text(encoding='utf-8')
    assert 'workflow_run:' in text
    assert 'workflows: ["review-artifact-validation"]' in text
    assert "github.event.workflow_run.conclusion == 'failure'" in text


def test_workflow_guards_pr_scope_and_same_repo_boundary() -> None:
    text = WORKFLOW_PATH.read_text(encoding='utf-8')
    assert "github.event.workflow_run.event == 'pull_request'" in text
    assert 'github.event.workflow_run.head_repository.full_name == github.repository' in text
    assert 'no_pr' in text


def test_workflow_uses_repo_native_entrypoint_and_persists_artifacts() -> None:
    text = WORKFLOW_PATH.read_text(encoding='utf-8')
    assert 'spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation' in text
    assert '.autofix/input/workflow_run_event.json' in text
    assert '.autofix/input/workflow_logs.txt' in text
    assert '.autofix/output/autofix_result.json' in text


def test_workflow_comments_and_enforces_fail_closed_terminal_step() -> None:
    text = WORKFLOW_PATH.read_text(encoding='utf-8')
    assert 'actions/github-script@v7' in text
    assert 'Fail-closed behavior is enforced' in text
    assert 'governed autofix blocked (fail-closed)' in text
