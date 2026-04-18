from __future__ import annotations

import json
from pathlib import Path

from scripts import run_three_letter_system_enforcement_audit as tle


def test_three_letter_audit_uses_shared_changed_file_helper(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / 'three_letter.json'

    monkeypatch.setattr(
        tle,
        '_parse_args',
        lambda: type(
            'Args',
            (),
            {
                'base_ref': 'base',
                'head_ref': 'head',
                'changed_files': [],
                'policy_path': 'docs/governance/three_letter_system_policy.json',
                'output': str(output_path),
            },
        )(),
    )

    seen: dict[str, object] = {}

    def fake_resolve_changed_files(**kwargs):
        seen.update(kwargs)
        return ['docs/architecture/system_registry.md']

    monkeypatch.setattr(tle, 'resolve_changed_files', fake_resolve_changed_files)
    monkeypatch.setattr(tle, 'parse_system_registry', lambda _path: {'systems': []})
    monkeypatch.setattr(
        tle,
        'evaluate_three_letter_system_enforcement',
        lambda **kwargs: {'final_decision': 'ALLOW', 'violations': [], 'changed_files': kwargs['changed_files']},
    )

    rc = tle.main()
    assert rc == 0
    assert seen['base_ref'] == 'base'
    assert seen['head_ref'] == 'head'

    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['changed_files'] == ['docs/architecture/system_registry.md']
