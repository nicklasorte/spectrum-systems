from __future__ import annotations

import pytest

from scripts import run_system_registry_guard as srg
from spectrum_systems.modules.governance.system_registry_guard import SystemRegistryGuardError


def test_resolve_changed_files_prefers_explicit_inputs() -> None:
    out = srg._resolve_changed_files("base", "head", ["b.py", "a.py", "a.py", ""])
    assert out == ["a.py", "b.py"]


def test_resolve_changed_files_uses_requested_range_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        srg,
        "_diff_name_only",
        lambda range_expr: (["x.py", "a.py"], None) if range_expr == "base..head" else (None, "unexpected"),
    )

    out = srg._resolve_changed_files("base", "head", [])
    assert out == ["x.py", "a.py"]


def test_resolve_changed_files_falls_back_to_origin_main_triple_dot(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_diff(range_expr: str) -> tuple[list[str] | None, str | None]:
        if range_expr == "base..head":
            return None, "invalid revision range"
        if range_expr == "origin/main...HEAD":
            return ["fallback.py"], None
        return None, "unexpected"

    monkeypatch.setattr(srg, "_diff_name_only", fake_diff)
    monkeypatch.setattr(srg, "_ref_exists", lambda ref: ref in {"origin/main", "HEAD"})

    out = srg._resolve_changed_files("base", "head", [])
    assert out == ["fallback.py"]


def test_resolve_changed_files_uses_merge_base_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_diff(range_expr: str) -> tuple[list[str] | None, str | None]:
        if range_expr in {"base..head", "origin/main...HEAD"}:
            return None, "invalid"
        if range_expr == "abc123..HEAD":
            return ["merge_base_file.py"], None
        return None, "unexpected"

    monkeypatch.setattr(srg, "_diff_name_only", fake_diff)
    monkeypatch.setattr(srg, "_ref_exists", lambda ref: ref in {"origin/main", "HEAD"})
    monkeypatch.setattr(srg, "_run", lambda command: (0, "abc123") if command == ["git", "merge-base", "origin/main", "HEAD"] else (1, "unexpected"))

    out = srg._resolve_changed_files("base", "head", [])
    assert out == ["merge_base_file.py"]


def test_resolve_changed_files_uses_head_parent_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(srg, "_diff_name_only", lambda range_expr: (["head_parent.py"], None) if range_expr == "HEAD~1..HEAD" else (None, "invalid"))
    monkeypatch.setattr(srg, "_ref_exists", lambda ref: ref == "HEAD~1")

    out = srg._resolve_changed_files("base", "head", [])
    assert out == ["head_parent.py"]


def test_resolve_changed_files_raises_with_attempt_details(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(srg, "_diff_name_only", lambda range_expr: (None, f"{range_expr} failed"))
    monkeypatch.setattr(srg, "_ref_exists", lambda ref: False)

    with pytest.raises(SystemRegistryGuardError) as exc:
        srg._resolve_changed_files("base", "head", [])

    message = str(exc.value)
    assert "requested_range=base..head" in message
    assert "fallback_origin_main_triple_dot" in message
    assert "fallback_merge_base" in message
    assert "fallback_head_parent" in message
