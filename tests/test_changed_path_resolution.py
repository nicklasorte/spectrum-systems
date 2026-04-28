from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime import changed_path_resolution as cpr


def _clear_github_context(monkeypatch) -> None:
    for key in ("GITHUB_EVENT_NAME", "GITHUB_BASE_SHA", "GITHUB_HEAD_SHA", "GITHUB_BEFORE_SHA", "GITHUB_SHA"):
        monkeypatch.delenv(key, raising=False)


def test_exact_diff_is_authoritative(monkeypatch):
    _clear_github_context(monkeypatch)
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
    _clear_github_context(monkeypatch)
    calls = []

    def fake_run(command, cwd):
        calls.append(command)
        if command[:3] == ["git", "cat-file", "-e"]:
            return cpr.CommandResult(returncode=1, stdout="", stderr="missing")
        if command[:2] == ["git", "fetch"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="fetch failed")
        if command == ["git", "diff", "--name-only", "base..missing"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="bad ref")
        if command == ["git", "diff", "--name-only", "base..HEAD"]:
            return cpr.CommandResult(returncode=0, stdout="contracts/schemas/x.schema.json\n", stderr="")
        if command == ["git", "status", "--porcelain"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="base", head_ref="missing")
    assert result.changed_paths == ["contracts/schemas/x.schema.json"]
    assert result.resolution_mode == "fetched_diff"
    assert result.trust_level == "bounded"
    assert any("base..HEAD" in ref for ref in result.refs_attempted)


def test_insufficient_context_blocks(monkeypatch):
    _clear_github_context(monkeypatch)
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


def test_pull_request_context_uses_github_sha_pair(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_BASE_SHA", "base-sha")
    monkeypatch.setenv("GITHUB_HEAD_SHA", "head-sha")

    def fake_run(command, cwd):
        if command[:3] == ["git", "cat-file", "-e"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        if command == ["git", "diff", "--name-only", "bad-base..bad-head"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="missing")
        if command == ["git", "diff", "--name-only", "base-sha..head-sha"]:
            return cpr.CommandResult(returncode=0, stdout="contracts/schemas/x.schema.json\n", stderr="")
        if command == ["git", "diff", "--name-only", "bad-base..HEAD"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="missing")
        if command == ["git", "status", "--porcelain"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        return cpr.CommandResult(returncode=1, stdout="", stderr="unexpected")

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="bad-base", head_ref="bad-head")
    assert result.changed_paths == ["contracts/schemas/x.schema.json"]
    assert result.changed_path_detection_mode == "github_pr_sha_pair"


def test_push_context_uses_before_sha_pair(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_BEFORE_SHA", "before-sha")
    monkeypatch.setenv("GITHUB_SHA", "after-sha")

    def fake_run(command, cwd):
        if command[:3] == ["git", "cat-file", "-e"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        if command == ["git", "diff", "--name-only", "missing..missing-head"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="missing")
        if command == ["git", "diff", "--name-only", "before-sha..after-sha"]:
            return cpr.CommandResult(returncode=0, stdout="scripts/build_preflight_pqx_wrapper.py\n", stderr="")
        if command == ["git", "diff", "--name-only", "missing..HEAD"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="missing")
        if command == ["git", "status", "--porcelain"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        return cpr.CommandResult(returncode=1, stdout="", stderr="unexpected")

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="missing", head_ref="missing-head")
    assert result.changed_path_detection_mode == "github_push_sha_pair"
    assert result.changed_paths == ["scripts/build_preflight_pqx_wrapper.py"]


def test_missing_refs_fail_closed_with_explicit_warning(monkeypatch):
    _clear_github_context(monkeypatch)
    def fake_run(command, cwd):
        if command[:3] == ["git", "diff", "--name-only"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="unknown revision")
        if command[:3] == ["git", "cat-file", "-e"]:
            return cpr.CommandResult(returncode=1, stdout="", stderr="missing")
        if command[:2] == ["git", "fetch"]:
            return cpr.CommandResult(returncode=128, stdout="", stderr="fetch failed")
        if command == ["git", "status", "--porcelain"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        if command == ["git", "diff", "--name-only", "HEAD"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        return cpr.CommandResult(returncode=1, stdout="", stderr="unexpected")

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="a", head_ref="b")
    assert result.insufficient_context is True
    assert any("unable to fetch required refs" in warning for warning in result.warnings)


def test_missing_sha_recovers_after_bounded_broad_fetch(monkeypatch):
    _clear_github_context(monkeypatch)
    calls = []

    def fake_run(command, cwd):
        calls.append(command)
        if command[:3] == ["git", "diff", "--name-only"]:
            if command[3] == "base..head":
                return cpr.CommandResult(returncode=128, stdout="", stderr="unknown revision")
            if command[3] == "base..HEAD":
                return cpr.CommandResult(returncode=0, stdout="scripts/run_contract_preflight.py\n", stderr="")
        if command[:3] == ["git", "cat-file", "-e"]:
            ref = command[3].replace("^{commit}", "")
            if ref in {"base", "head"}:
                # Initially missing, then present after broad fetch.
                broad_fetch_seen = any(cmd == ["git", "fetch", "--no-tags", "--depth=2000", "origin"] for cmd in calls)
                return cpr.CommandResult(returncode=0 if broad_fetch_seen else 1, stdout="", stderr="")
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        if command[:2] == ["git", "fetch"]:
            if command == ["git", "fetch", "--no-tags", "--depth=1", "origin", "base"]:
                return cpr.CommandResult(returncode=128, stdout="", stderr="server does not allow direct SHA fetch")
            if command == ["git", "fetch", "--no-tags", "--depth=1", "origin", "head"]:
                return cpr.CommandResult(returncode=128, stdout="", stderr="server does not allow direct SHA fetch")
            if command == ["git", "fetch", "--no-tags", "--depth=2000", "origin"]:
                return cpr.CommandResult(returncode=0, stdout="", stderr="")
        if command == ["git", "status", "--porcelain"]:
            return cpr.CommandResult(returncode=0, stdout="", stderr="")
        return cpr.CommandResult(returncode=1, stdout="", stderr="unexpected")

    monkeypatch.setattr(cpr, "_run", fake_run)
    result = cpr.resolve_changed_paths(repo_root=Path("."), base_ref="base", head_ref="head")
    assert result.insufficient_context is False
    assert result.changed_paths == ["scripts/run_contract_preflight.py"]
    assert any(cmd == ["git", "fetch", "--no-tags", "--depth=2000", "origin"] for cmd in calls)
