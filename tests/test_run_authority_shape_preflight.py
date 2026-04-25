"""CLI surface tests for ``scripts/run_authority_shape_preflight.py``."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import run_authority_shape_preflight as preflight_cli


def _make_args(**overrides):
    defaults = {
        "base_ref": "base",
        "head_ref": "head",
        "changed_files": [],
        "vocabulary": "contracts/governance/authority_shape_vocabulary.json",
        "output": "outputs/authority_shape_preflight/_test_result.json",
        "mode": "suggest-only",
    }
    defaults.update(overrides)
    return type("Args", (), defaults)()


def test_cli_returns_zero_when_no_violations(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    monkeypatch.setattr(
        preflight_cli,
        "_parse_args",
        lambda: _make_args(output=str(output_path), mode="suggest-only"),
    )
    monkeypatch.setattr(
        preflight_cli,
        "resolve_changed_files",
        lambda **_: [],
    )
    rc = preflight_cli.main()
    assert rc == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["mode"] == "suggest-only"


def test_cli_returns_nonzero_on_violation(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    repo_root = preflight_cli.REPO_ROOT
    sandbox_rel = "scripts/_tmp_authority_shape_violation.py"
    sandbox_path = repo_root / sandbox_rel
    sandbox_path.parent.mkdir(parents=True, exist_ok=True)
    sandbox_path.write_text("promotion_decision = 'pending'\n", encoding="utf-8")

    monkeypatch.setattr(
        preflight_cli,
        "_parse_args",
        lambda: _make_args(output=str(output_path), mode="suggest-only"),
    )
    monkeypatch.setattr(
        preflight_cli,
        "resolve_changed_files",
        lambda **_: [sandbox_rel],
    )
    try:
        rc = preflight_cli.main()
    finally:
        sandbox_path.unlink(missing_ok=True)
    assert rc == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["summary"]["violation_count"] >= 1
    assert any(v["cluster"] in {"promotion", "decision"} for v in payload["violations"])


def test_cli_propagates_changed_file_resolution_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        preflight_cli,
        "_parse_args",
        lambda: _make_args(output=str(tmp_path / "result.json")),
    )

    def _raise(**_kwargs):
        raise preflight_cli.ChangedFilesResolutionError("bad refs")

    monkeypatch.setattr(preflight_cli, "resolve_changed_files", _raise)
    try:
        preflight_cli.main()
    except preflight_cli.AuthorityShapePreflightError as exc:
        assert "bad refs" in str(exc)
    else:
        raise AssertionError("expected AuthorityShapePreflightError")
