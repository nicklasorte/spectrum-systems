"""Phase 2 (TLS-02) — classification correctness tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.tls_dependency_graph.classification import classify_systems
from spectrum_systems.modules.tls_dependency_graph.evidence_scanner import attach_evidence
from spectrum_systems.modules.tls_dependency_graph.registry_parser import build_dependency_graph


def _build(registry_fixture_path: Path, repo_fixture: Path):
    graph = build_dependency_graph(registry_fixture_path)
    evidence = attach_evidence(graph, repo_root=repo_fixture)
    return graph, evidence


def test_active_systems_classified_as_active_when_evidence_present(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    for sid in ("AEX", "PQX", "EVL", "REP", "LIN"):
        assert by_sid[sid]["classification"] == "active_system", sid


def test_active_in_registry_without_evidence_is_unknown(registry_fixture_path: Path, tmp_path: Path) -> None:
    graph = build_dependency_graph(registry_fixture_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    evidence = attach_evidence(graph, repo_root=empty)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["AEX"]["classification"] == "unknown"
    assert by_sid["AEX"]["reason"] == "active_in_registry_but_no_repo_evidence"


def test_h01_is_h_slice(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence, repo_detected_candidates=["H01"])
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["H01"]["classification"] == "h_slice"


def test_rfx_is_unknown_when_only_repo_detected(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence, repo_detected_candidates=["RFX"])
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["RFX"]["classification"] == "unknown"
    assert by_sid["RFX"]["reason"] == "repo_only_candidate_no_registry_record"


def test_hop_classified_from_registry(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    if "HOP" not in by_sid:
        pytest.skip("fixture does not include HOP")
    assert by_sid["HOP"]["classification"] == "active_system"


def test_met_systems_are_unknown_unless_proven(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    # MET is added by default and not in the fixture registry — must be unknown.
    assert by_sid["MET"]["classification"] == "unknown"
    assert "MET_unknown_unless_proven" in by_sid["MET"]["reason"]
    assert by_sid["METS"]["classification"] == "unknown"


def test_deprecated_marked_deprecated(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["HNX"]["classification"] == "deprecated"


def test_support_marked_support(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["SUP"]["classification"] == "support_capability"


def test_future_marked_future(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["ABX"]["classification"] == "future"


def test_no_candidate_misclassified_as_active_without_registry_evidence(
    registry_fixture_path: Path, repo_fixture: Path
) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence, repo_detected_candidates=["FOO"])
    by_sid = {c["system_id"]: c for c in out["candidates"]}
    assert by_sid["FOO"]["classification"] == "unknown"


def test_ambiguous_systems_listed_explicitly(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence = _build(registry_fixture_path, repo_fixture)
    out = classify_systems(graph, evidence)
    ambiguous_ids = {c["system_id"] for c in out["ambiguous_systems"]}
    assert "MET" in ambiguous_ids
    assert "METS" in ambiguous_ids
    assert "RFX" in ambiguous_ids
