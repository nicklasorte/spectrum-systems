from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_system_registry_guard as srg
from spectrum_systems.modules.governance.system_registry_guard import SystemRegistryGuardError


def test_resolve_changed_files_passthrough_to_shared_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_changed_files(**kwargs):
        captured.update(kwargs)
        return ['a.py', 'b.py']

    monkeypatch.setattr(srg, 'resolve_changed_files', fake_resolve_changed_files)
    changed_files = srg.resolve_changed_files(
        repo_root=Path('.'),
        base_ref='base',
        head_ref='head',
        explicit_changed_files=['b.py', 'a.py'],
    )

    assert changed_files == ['a.py', 'b.py']
    assert captured['base_ref'] == 'base'
    assert captured['head_ref'] == 'head'


def test_main_maps_shared_helper_error_to_guard_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(srg, '_parse_args', lambda: type('Args', (), {
        'base_ref': 'base',
        'head_ref': 'head',
        'changed_files': [],
        'output': 'outputs/system_registry_guard/test_resolution.json',
    })())

    monkeypatch.setattr(
        srg,
        'resolve_changed_files',
        lambda **kwargs: (_ for _ in ()).throw(srg.ChangedFilesResolutionError('resolution failed')),
    )

    with pytest.raises(SystemRegistryGuardError) as exc:
        srg.main()

    assert 'resolution failed' in str(exc.value)
