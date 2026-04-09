from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation import (
    GovernedAutofixError,
    enforce_entry_invariant,
    enforce_replay_gate,
    run_governed_autofix,
)


def test_entry_invariant_fails_closed_when_artifacts_missing() -> None:
    with pytest.raises(GovernedAutofixError, match='entry_invariant_missing'):
        enforce_entry_invariant({'build_admission_record': {}})


def test_replay_gate_fails_closed_on_missing_or_failed_result() -> None:
    with pytest.raises(GovernedAutofixError, match='validation_replay_missing'):
        enforce_replay_gate(None)  # type: ignore[arg-type]

    with pytest.raises(GovernedAutofixError, match='validation_replay_failed'):
        enforce_replay_gate({'artifact_type': 'validation_result_record', 'passed': False})


def test_run_governed_autofix_blocks_without_safe_fix_plan(tmp_path: Path) -> None:
    event_payload = {
        'repository': {'full_name': 'nicklasorte/spectrum-systems'},
        'workflow_run': {
            'id': 123,
            'head_branch': 'feature/test',
            'head_repository': {'full_name': 'nicklasorte/spectrum-systems'},
            'pull_requests': [{'number': 9}],
        },
    }
    event_path = tmp_path / 'event.json'
    event_path.write_text(json.dumps(event_payload), encoding='utf-8')

    logs_path = tmp_path / 'logs.txt'
    logs_path.write_text('pytest failure output', encoding='utf-8')

    out = run_governed_autofix(
        event_payload_path=event_path,
        logs_path=logs_path,
        output_dir=tmp_path / 'out',
        repo_root=tmp_path,
        push=False,
    )

    assert out['status'] == 'blocked'
    assert out['reason'] == 'no_safe_fix_found'
    assert out['lineage_present'] is True
    assert out['validation_replay_passed'] is False


def test_run_governed_autofix_fails_closed_for_fork_pr(tmp_path: Path) -> None:
    event_payload = {
        'repository': {'full_name': 'nicklasorte/spectrum-systems'},
        'workflow_run': {
            'id': 999,
            'head_branch': 'feature/test',
            'head_repository': {'full_name': 'attacker/spectrum-systems'},
            'pull_requests': [{'number': 7}],
        },
    }
    event_path = tmp_path / 'event.json'
    event_path.write_text(json.dumps(event_payload), encoding='utf-8')
    logs_path = tmp_path / 'logs.txt'
    logs_path.write_text('non-empty logs', encoding='utf-8')

    with pytest.raises(GovernedAutofixError, match='fork_pr'):
        run_governed_autofix(
            event_payload_path=event_path,
            logs_path=logs_path,
            output_dir=tmp_path / 'out',
            repo_root=tmp_path,
            push=False,
        )
