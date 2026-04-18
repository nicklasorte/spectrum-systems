from __future__ import annotations

import json
from pathlib import Path

from scripts import run_authority_leak_guard as alg


def test_authority_guard_uses_shared_changed_file_helper(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / 'authority_result.json'

    monkeypatch.setattr(
        alg,
        '_parse_args',
        lambda: type(
            'Args',
            (),
            {
                'base_ref': 'base',
                'head_ref': 'head',
                'changed_files': [],
                'registry': 'contracts/governance/authority_registry.json',
                'output': str(output_path),
            },
        )(),
    )

    called: dict[str, object] = {}

    def fake_resolve_changed_files(**kwargs):
        called.update(kwargs)
        return ['README.md']

    monkeypatch.setattr(alg, 'resolve_changed_files', fake_resolve_changed_files)
    monkeypatch.setattr(alg, 'load_authority_registry', lambda _path: {'owners': []})
    monkeypatch.setattr(alg, 'find_forbidden_vocabulary', lambda _path, _registry: [])
    monkeypatch.setattr(alg, 'detect_authority_shapes', lambda _path, _registry: [])

    rc = alg.main()
    assert rc == 0
    assert called['base_ref'] == 'base'
    assert called['head_ref'] == 'head'

    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['changed_files'] == ['README.md']


def test_authority_guard_maps_shared_helper_errors(monkeypatch: object) -> None:
    monkeypatch.setattr(
        alg,
        '_parse_args',
        lambda: type(
            'Args',
            (),
            {
                'base_ref': 'base',
                'head_ref': 'head',
                'changed_files': [],
                'registry': 'contracts/governance/authority_registry.json',
                'output': 'outputs/authority_leak_guard/test_result.json',
            },
        )(),
    )

    monkeypatch.setattr(
        alg,
        'resolve_changed_files',
        lambda **kwargs: (_ for _ in ()).throw(alg.ChangedFilesResolutionError('bad refs')),
    )

    try:
        alg.main()
    except alg.AuthorityLeakGuardError as exc:
        assert 'bad refs' in str(exc)
    else:
        raise AssertionError('expected AuthorityLeakGuardError')
