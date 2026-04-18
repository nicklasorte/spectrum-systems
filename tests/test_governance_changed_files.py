from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.governance import changed_files as cf


def test_explicit_changed_files_passthrough_is_normalized() -> None:
    out = cf.resolve_changed_files(
        repo_root=Path('.'),
        base_ref='base',
        head_ref='head',
        explicit_changed_files=['b.py', 'a.py', 'a.py', ''],
    )
    assert out == ['a.py', 'b.py']


def test_valid_base_head_diff_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], *, repo_root: Path) -> tuple[int, str]:
        assert repo_root == Path('.')
        if command == ['git', 'diff', '--name-only', 'base..head']:
            return 0, 'z.py\na.py\n'
        raise AssertionError(command)

    out = cf.resolve_changed_files(
        repo_root=Path('.'),
        base_ref='base',
        head_ref='head',
        explicit_changed_files=[],
        runner=fake_run,
    )
    assert out == ['a.py', 'z.py']


def test_invalid_revision_range_falls_back_to_origin_main_triple_dot() -> None:
    def fake_run(command: list[str], *, repo_root: Path) -> tuple[int, str]:
        if command == ['git', 'diff', '--name-only', 'base..head']:
            return 128, 'invalid revision range'
        if command == ['git', 'rev-parse', '--verify', 'origin/main^{commit}']:
            return 0, 'ok'
        if command == ['git', 'rev-parse', '--verify', 'HEAD^{commit}']:
            return 0, 'ok'
        if command == ['git', 'diff', '--name-only', 'origin/main...HEAD']:
            return 0, 'contracts/a.json\ncontracts/b.json\n'
        raise AssertionError(command)

    out = cf.resolve_changed_files(
        repo_root=Path('.'),
        base_ref='base',
        head_ref='head',
        explicit_changed_files=[],
        runner=fake_run,
    )
    assert out == ['contracts/a.json', 'contracts/b.json']


def test_empty_unknown_git_state_fallback_uses_head_working_tree() -> None:
    def fake_run(command: list[str], *, repo_root: Path) -> tuple[int, str]:
        if command == ['git', 'diff', '--name-only', 'base..head']:
            return 128, 'missing'
        if command == ['git', 'rev-parse', '--verify', 'origin/main^{commit}']:
            return 1, 'missing'
        if command == ['git', 'rev-parse', '--verify', 'HEAD~1^{commit}']:
            return 1, 'missing'
        if command == ['git', 'diff', '--name-only', 'HEAD']:
            return 0, ''
        raise AssertionError(command)

    out = cf.resolve_changed_files(
        repo_root=Path('.'),
        base_ref='base',
        head_ref='head',
        explicit_changed_files=[],
        runner=fake_run,
    )
    assert out == []


def test_failure_raises_with_attempt_details() -> None:
    def fake_run(command: list[str], *, repo_root: Path) -> tuple[int, str]:
        if command[:3] == ['git', 'diff', '--name-only']:
            return 128, 'bad revision'
        if command[:3] == ['git', 'rev-parse', '--verify']:
            return 1, 'missing'
        raise AssertionError(command)

    with pytest.raises(cf.ChangedFilesResolutionError) as exc:
        cf.resolve_changed_files(
            repo_root=Path('.'),
            base_ref='base',
            head_ref='head',
            explicit_changed_files=[],
            runner=fake_run,
        )

    message = str(exc.value)
    assert 'requested_range=base..head' in message
    assert 'fallback_head_parent' in message
    assert 'fallback_working_tree' in message
