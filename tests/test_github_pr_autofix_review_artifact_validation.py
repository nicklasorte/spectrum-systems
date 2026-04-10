from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation import (
    GovernedAutofixError,
    _narrow_test_targets_if_safe,
    enforce_artifact_spine,
    enforce_entry_invariant,
    enforce_governance_signal,
    enforce_preflight_gate,
    enforce_repair_validation_linkage,
    enforce_replay_gate,
    run_governed_autofix,
    scan_review_governance_radar,
    run_validation_replay,
)


def test_entry_invariant_fails_closed_when_artifacts_missing() -> None:
    with pytest.raises(GovernedAutofixError, match='entry_invariant_missing'):
        enforce_entry_invariant({'build_admission_record': {}})


def test_replay_gate_fails_closed_on_missing_or_failed_result() -> None:
    with pytest.raises(GovernedAutofixError, match='validation_replay_missing'):
        enforce_replay_gate(None)  # type: ignore[arg-type]

    with pytest.raises(GovernedAutofixError, match='validation_replay_failed'):
        enforce_replay_gate({'artifact_type': 'validation_result_record', 'passed': False})


def test_repair_attempt_requires_validation_linkage() -> None:
    with pytest.raises(GovernedAutofixError, match='repair_validation_link_missing'):
        enforce_repair_validation_linkage({'artifact_type': 'repair_attempt_record', 'validation_result_ref': ''})


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
        repo_root=_init_git_repo(tmp_path),
        push=False,
    )

    assert out['status'] == 'blocked'
    assert out['reason'] == 'no_safe_fix_found'
    assert out['lineage_present'] is True
    assert out['validation_replay_passed'] is False
    repair_attempt = json.loads((tmp_path / 'out' / 'artifacts' / 'repair_attempt_record.json').read_text(encoding='utf-8'))
    assert repair_attempt['artifact_type'] == 'repair_attempt_record'
    assert repair_attempt['execution_outcome'] == 'no_safe_fix'
    assert repair_attempt['push_outcome'] == 'no_safe_fix'


def _init_git_repo(tmp_path: Path) -> Path:
    subprocess.run(['git', 'init'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'checkout', '-b', 'feature/test'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'remote', 'add', 'origin', 'https://github.com/nicklasorte/spectrum-systems.git'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    (tmp_path / 'requirements-dev.txt').write_text('', encoding='utf-8')
    (tmp_path / 'scripts').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'docs' / 'reviews').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'scripts' / 'validate-review-artifacts.js').write_text('console.log("ok")\n', encoding='utf-8')
    (tmp_path / 'scripts' / 'check_review_registry.py').write_text('print("ok")\n', encoding='utf-8')
    (tmp_path / 'docs' / 'reviews' / 'review-registry.json').write_text('[]\n', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    return tmp_path


def test_run_governed_autofix_applies_bounded_fix_and_commits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root = _init_git_repo(tmp_path)
    target = repo_root / 'tests' / 'test_demo.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('def test_demo():\n    assert 1 == 2\n', encoding='utf-8')
    subprocess.run(['git', 'add', str(target)], cwd=str(repo_root), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'commit', '-m', 'introduce failure'], cwd=str(repo_root), check=True, capture_output=True, text=True)

    event_payload = {
        'repository': {'full_name': 'nicklasorte/spectrum-systems'},
        'workflow_run': {
            'id': 321,
            'head_branch': 'feature/test',
            'head_repository': {'full_name': 'nicklasorte/spectrum-systems'},
            'pull_requests': [{'number': 12}],
        },
    }
    event_path = repo_root / 'event.json'
    event_path.write_text(json.dumps(event_payload), encoding='utf-8')
    logs_path = repo_root / 'logs.txt'
    logs_path.write_text('pytest\n tests/test_demo.py:2: AssertionError\n E assert 1 == 2\n', encoding='utf-8')

    monkeypatch.setattr(
        'spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation.run_validation_replay',
        lambda **_: {
            'artifact_type': 'validation_result_record',
            'validation_result_id': '',
            'attempt_id': '',
            'admission_ref': '',
            'trace_id': '',
            'workflow_equivalent': 'review-artifact-validation',
            'validation_target': {'type': 'repo_branch', 'value': 'feature/test'},
            'validation_scope': 'narrow',
            'validation_path': 'pre_push_replay',
            'commands': [{'command': 'pytest tests/test_demo.py', 'exit_code': 0, 'stdout_excerpt': '', 'stderr_excerpt': ''}],
            'status': 'passed',
            'blocking_reason': None,
            'failure_summary': None,
            'enforcement_owner': 'SEL',
            'passed': True,
            'emitted_at': '2026-04-09T00:00:00Z',
        },
    )

    out = run_governed_autofix(
        event_payload_path=event_path,
        logs_path=logs_path,
        output_dir=repo_root / 'out',
        repo_root=repo_root,
        push=False,
    )
    assert out['status'] == 'validated_committed_no_push'
    assert out['validation_replay_passed'] is True
    assert out['repair_applied'] is True
    assert (repo_root / 'tests' / 'test_demo.py').read_text(encoding='utf-8').endswith('assert 1 == 1\n')
    admission_record = json.loads((repo_root / 'out' / 'artifacts' / 'build_admission_record.json').read_text(encoding='utf-8'))
    assert admission_record['request_source']['owner'] == 'AEX'
    assert admission_record['request_source']['source_workflow']['workflow'] == 'review-artifact-validation'
    assert admission_record['repo_mutation_classification']['repo_mutation_requested'] is True
    validation_record = json.loads((repo_root / 'out' / 'artifacts' / 'validation_result_record.json').read_text(encoding='utf-8'))
    assert validation_record['artifact_type'] == 'validation_result_record'
    assert validation_record['validation_scope'] == 'narrow'
    assert validation_record['status'] == 'passed'
    repair_attempt = json.loads((repo_root / 'out' / 'artifacts' / 'repair_attempt_record.json').read_text(encoding='utf-8'))
    assert repair_attempt['artifact_type'] == 'repair_attempt_record'
    assert repair_attempt['owner'] == 'FRE'
    assert repair_attempt['validation_result_ref'].startswith('validation_result_record:')
    assert repair_attempt['push_outcome'] == 'blocked'
    preflight = json.loads((repo_root / 'out' / 'artifacts' / 'contract_preflight_result_artifact.json').read_text(encoding='utf-8'))
    assert preflight['artifact_type'] == 'contract_preflight_result_artifact'
    assert preflight['status'] == 'passed'
    assert preflight['strategy_gate_decision'] == 'ALLOW'


def test_narrowing_is_blocked_when_multilayer_failure_signal_present() -> None:
    event_logs = 'pytest\ncheck_review_registry.py failed\n tests/test_demo.py:2: AssertionError\n E assert 1 == 2\n'
    # helper should reject narrowing under cross-layer failure signal
    from spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation import RepairAction

    targets = _narrow_test_targets_if_safe(
        actions=[
            RepairAction(
                action_id='a',
                action_type='text_replace',
                target_path='tests/test_demo.py',
                match_text='assert 1 == 2',
                replacement_text='assert 1 == 1',
                rationale='bounded',
            )
        ],
        logs_text=event_logs,
    )
    assert targets is None


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
            repo_root=_init_git_repo(tmp_path),
            push=False,
        )


def test_run_governed_autofix_fails_closed_for_missing_logs(tmp_path: Path) -> None:
    repo_root = _init_git_repo(tmp_path)
    event_payload = {
        'repository': {'full_name': 'nicklasorte/spectrum-systems'},
        'workflow_run': {
            'id': 444,
            'head_branch': 'feature/test',
            'head_repository': {'full_name': 'nicklasorte/spectrum-systems'},
            'pull_requests': [{'number': 3}],
        },
    }
    event_path = repo_root / 'event.json'
    event_path.write_text(json.dumps(event_payload), encoding='utf-8')
    with pytest.raises(GovernedAutofixError, match='logs_missing'):
        run_governed_autofix(
            event_payload_path=event_path,
            logs_path=repo_root / 'missing-logs.txt',
            output_dir=repo_root / 'out',
            repo_root=repo_root,
            push=False,
        )


def test_push_path_rejects_github_token_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root = _init_git_repo(tmp_path)
    target = repo_root / 'tests' / 'test_push_demo.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('def test_push_demo():\n    assert 1 == 2\n', encoding='utf-8')
    subprocess.run(['git', 'add', str(target)], cwd=str(repo_root), check=True, capture_output=True, text=True)
    subprocess.run(['git', 'commit', '-m', 'introduce push failure'], cwd=str(repo_root), check=True, capture_output=True, text=True)

    event_payload = {
        'repository': {'full_name': 'nicklasorte/spectrum-systems'},
        'workflow_run': {
            'id': 777,
            'head_branch': 'feature/test',
            'head_repository': {'full_name': 'nicklasorte/spectrum-systems'},
            'pull_requests': [{'number': 77}],
        },
    }
    event_path = repo_root / 'event.json'
    event_path.write_text(json.dumps(event_payload), encoding='utf-8')
    logs_path = repo_root / 'logs.txt'
    logs_path.write_text('pytest\n tests/test_push_demo.py:2: AssertionError\n E assert 1 == 2\n', encoding='utf-8')
    monkeypatch.setenv('GITHUB_TOKEN', 'ghs-only-not-allowed')
    monkeypatch.delenv('AUTOFIX_PUSH_TOKEN', raising=False)
    monkeypatch.delenv('GITHUB_APP_TOKEN', raising=False)
    monkeypatch.setattr(
        'spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation.run_validation_replay',
        lambda **_: {
            'artifact_type': 'validation_result_record',
            'validation_result_id': '',
            'attempt_id': '',
            'admission_ref': '',
            'trace_id': '',
            'workflow_equivalent': 'review-artifact-validation',
            'validation_target': {'type': 'repo_branch', 'value': 'feature/test'},
            'validation_scope': 'narrow',
            'validation_path': 'pre_push_replay',
            'commands': [{'command': 'pytest tests/test_push_demo.py', 'exit_code': 0, 'stdout_excerpt': '', 'stderr_excerpt': ''}],
            'status': 'passed',
            'blocking_reason': None,
            'failure_summary': None,
            'enforcement_owner': 'SEL',
            'passed': True,
            'emitted_at': '2026-04-09T00:00:00Z',
        },
    )

    with pytest.raises(GovernedAutofixError, match='push_token_missing'):
        run_governed_autofix(
            event_payload_path=event_path,
            logs_path=logs_path,
            output_dir=repo_root / 'out',
            repo_root=repo_root,
            push=True,
        )


def test_preflight_required_for_progression() -> None:
    with pytest.raises(GovernedAutofixError, match='preflight_artifact_missing_or_ambiguous'):
        enforce_preflight_gate({'artifact_type': 'wrong'})


def test_preflight_block_fails_closed() -> None:
    with pytest.raises(GovernedAutofixError, match='preflight_strategy_gate_blocked'):
        enforce_preflight_gate(
            {
                'artifact_type': 'contract_preflight_result_artifact',
                'status': 'failed',
                'invariant_violations': ['missing_tlc_handoff_record'],
                'strategy_gate_decision': 'BLOCK',
            }
        )


def test_validation_entrypoint_consistency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root = _init_git_repo(tmp_path)
    expected = {
        'artifact_type': 'validation_result_record',
        'validation_result_id': '',
        'attempt_id': '',
        'admission_ref': '',
        'trace_id': '',
        'workflow_equivalent': 'review-artifact-validation',
        'validation_target': {'type': 'repo_branch', 'value': ''},
        'validation_scope': 'narrow',
        'validation_path': 'pre_push_replay',
        'commands': [],
        'status': 'passed',
        'blocking_reason': None,
        'failure_summary': None,
        'enforcement_owner': 'SEL',
        'execution_owner': 'PQX',
        'passed': True,
        'emitted_at': '2026-04-10T00:00:00Z',
    }
    output_path = repo_root / '.autofix' / 'runtime_validation_result.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(expected), encoding='utf-8')

    seen: dict[str, object] = {}

    def fake_run(command: list[str], *, cwd: Path) -> object:
        seen['command'] = command
        seen['cwd'] = cwd
        return type('Res', (), {'command': ' '.join(command), 'exit_code': 0, 'stdout_excerpt': '', 'stderr_excerpt': ''})()

    monkeypatch.setattr(
        'spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation._run_command',
        fake_run,
    )
    payload = run_validation_replay(repo_root=repo_root, narrow_test_targets=['tests/test_demo.py'])
    assert payload == expected
    assert seen['cwd'] == repo_root
    assert seen['command'] == [
        'python',
        'scripts/run_review_artifact_validation.py',
        '--repo-root',
        '.',
        '--output-json',
        str(output_path),
        '--targets',
        'tests/test_demo.py',
    ]


def test_artifact_spine_enforced() -> None:
    enforce_artifact_spine(
        {
            'build_admission_record': {'artifact_type': 'build_admission_record'},
            'validation_result_record': {'artifact_type': 'validation_result_record', 'passed': True},
            'repair_attempt_record': {'artifact_type': 'repair_attempt_record'},
        }
    )


def test_missing_artifact_fails_closed() -> None:
    with pytest.raises(GovernedAutofixError, match='artifact_spine_missing'):
        enforce_artifact_spine({'build_admission_record': {}, 'validation_result_record': {}})


def test_governance_radar_detects_overdue(tmp_path: Path) -> None:
    repo_root = _init_git_repo(tmp_path)
    (repo_root / 'docs' / 'reviews' / 'review-registry.json').write_text(
        json.dumps(
            [
                {
                    'review_id': 'RVW-OVERDUE',
                    'status': 'In Progress',
                    'follow_up_due_date': '2026-04-01',
                    'follow_up_trigger': 'pending fix verification',
                }
            ]
        ),
        encoding='utf-8',
    )
    signal = scan_review_governance_radar(repo_root=repo_root)
    assert signal['artifact_type'] == 'review_governance_signal_artifact'
    assert signal['risk_level'] == 'OVERDUE'
    assert signal['status'] == 'blocked'
    assert signal['affected_reviews'][0]['review_id'] == 'RVW-OVERDUE'


def test_governance_signal_integrates_with_preflight() -> None:
    enforce_governance_signal(
        {
            'artifact_type': 'review_governance_signal_artifact',
            'status': 'ok',
            'risk_level': 'WARNING',
            'affected_reviews': [{'review_id': 'RVW-WARN'}],
            'due_windows': {'overdue': 0, 'due_soon': 1, 'missing': 0, 'future': 0},
        }
    )


def test_overdue_blocks_execution() -> None:
    with pytest.raises(GovernedAutofixError, match='review_governance_signal_overdue_blocked'):
        enforce_governance_signal(
            {
                'artifact_type': 'review_governance_signal_artifact',
                'status': 'blocked',
                'risk_level': 'OVERDUE',
                'affected_reviews': [{'review_id': 'RVW-OVERDUE'}],
                'due_windows': {'overdue': 1, 'due_soon': 0, 'missing': 0, 'future': 0},
            }
        )
