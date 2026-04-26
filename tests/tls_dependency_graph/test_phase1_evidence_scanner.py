"""Phase 1 (TLS-01) — evidence scanner tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.tls_dependency_graph.evidence_scanner import attach_evidence
from spectrum_systems.modules.tls_dependency_graph.registry_parser import build_dependency_graph


def test_evidence_scanner_attaches_evidence_for_every_system(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph = build_dependency_graph(registry_fixture_path)
    out = attach_evidence(graph, repo_root=repo_fixture)
    sids = {row["system_id"] for row in out["systems"]}
    assert sids == {n["system_id"] for n in graph["active_systems"]}


def test_evidence_scanner_picks_up_module_paths(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph = build_dependency_graph(registry_fixture_path)
    out = attach_evidence(graph, repo_root=repo_fixture)
    aex_row = next(r for r in out["systems"] if r["system_id"] == "AEX")
    assert any(
        path.endswith("agent_golden_path.py") for path in aex_row["evidence"]["modules"]
    )


def test_evidence_scanner_picks_up_tests(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph = build_dependency_graph(registry_fixture_path)
    out = attach_evidence(graph, repo_root=repo_fixture)
    aex_row = next(r for r in out["systems"] if r["system_id"] == "AEX")
    evl_row = next(r for r in out["systems"] if r["system_id"] == "EVL")
    assert any("test_aex" in p for p in aex_row["evidence"]["tests"])
    assert any("test_evl_eval" in p for p in evl_row["evidence"]["tests"])


def test_evidence_scanner_marks_missing_evidence_explicitly(registry_fixture_path: Path, tmp_path: Path) -> None:
    """Empty repo: every system must be present with has_evidence=False and a reason."""

    empty_root = tmp_path / "empty_repo"
    empty_root.mkdir()
    graph = build_dependency_graph(registry_fixture_path)
    out = attach_evidence(graph, repo_root=empty_root)
    for row in out["systems"]:
        assert row["has_evidence"] is False
        assert row["missing_evidence_reason"] is not None
        assert row["evidence_count"] == 0


def test_evidence_scanner_does_not_silently_skip_systems(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph = build_dependency_graph(registry_fixture_path)
    out = attach_evidence(graph, repo_root=repo_fixture)
    # one row per active system, no fewer
    assert len(out["systems"]) == len(graph["active_systems"])


def test_evidence_scanner_raises_when_no_active_systems() -> None:
    with pytest.raises(ValueError):
        attach_evidence({"active_systems": []})
