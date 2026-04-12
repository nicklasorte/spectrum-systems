from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime import changed_path_resolution as cpr


def test_exact_diff_is_authoritative(monkeypatch):
    def fake_run(command, cwd):
        if command[:3] == ["git", "diff", "--name-only"]:
            return cpr.CommandResult(returncode=0, stdout="a.py\nb.py\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="base", head_ref="head")
    assert result.changed_paths == ["a.py", "b.py"]
    assert result.resolution_mode == "exact_diff"
    assert result.trust_level == "authoritative"
    assert result.bounded_runtime is True


def test_invalid_ref_falls_back_to_fetched_diff(monkeypatch):
    calls = []

    def fake_run(command, cwd):
        calls.append(command)
        if command == ["git", "diff", "--name-only", "base..missing"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="bad ref")
        if command == ["git", "diff", "--name-only", "base..HEAD"]:
            return cpr.CommandResult(returncode=0, stdout="contracts/schemas/x.schema.json\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="base", head_ref="missing")
    assert result.changed_paths == ["contracts/schemas/x.schema.json"]
    assert result.resolution_mode == "fetched_diff"
    assert result.trust_level == "bounded"
    assert any("base..HEAD" in ref for ref in result.refs_attempted)


def test_insufficient_context_blocks(monkeypatch):
    def fake_run(command, cwd):
        if command[:3] == ["git", "diff", "--name-only"]:
            return cpr.CommandResult(returncode=1, stdout="", stderr="no diff")
        if command == ["git", "status", "--porcelain"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        return cpr.CommandResult(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="base", head_ref="head")
    assert result.insufficient_context is True
    assert result.changed_paths == []
    assert result.trust_level == "insufficient"
