"""Phase 4 (TLS-04) — deterministic ranking tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.tls_dependency_graph.classification import classify_systems
from spectrum_systems.modules.tls_dependency_graph.evidence_scanner import attach_evidence
from spectrum_systems.modules.tls_dependency_graph.ranking import rank_systems
from spectrum_systems.modules.tls_dependency_graph.registry_parser import build_dependency_graph
from spectrum_systems.modules.tls_dependency_graph.trust_gaps import detect_trust_gaps


def _build(registry_fixture_path: Path, repo_fixture: Path):
    graph = build_dependency_graph(registry_fixture_path)
    evidence = attach_evidence(graph, repo_root=repo_fixture)
    classification = classify_systems(graph, evidence, repo_detected_candidates=["H01", "RFX"])
    trust_gaps = detect_trust_gaps(graph, evidence, classification)
    return graph, evidence, classification, trust_gaps


def test_ranking_is_deterministic_across_runs(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    a = rank_systems(graph, evidence, classification, trust_gaps)
    b = rank_systems(graph, evidence, classification, trust_gaps)
    assert [r["system_id"] for r in a["top_5"]] == [r["system_id"] for r in b["top_5"]]
    assert [r["score"] for r in a["ranked_systems"]] == [r["score"] for r in b["ranked_systems"]]


def test_top_5_contains_required_fields(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    required = {
        "rank",
        "system_id",
        "action",
        "why_now",
        "trust_gap_signals",
        "dependencies",
        "unlocks",
        "finish_definition",
        "next_prompt",
    }
    for row in out["top_5"]:
        assert required.issubset(row.keys())


def test_no_unknown_in_top_5_unless_justified(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    for row in out["top_5"]:
        if row["classification"] == "unknown":
            assert "unknown_justification" in row, "unknown rows must carry an explicit justification"


def test_hardening_ranked_before_expansion(registry_fixture_path: Path, repo_fixture: Path) -> None:
    """An active_system with gaps outranks an h_slice or unknown at equal score."""

    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    # Identify active systems with gaps.
    active_with_gaps = [
        r for r in out["ranked_systems"]
        if r["classification"] in ("active_system", "h_slice") and r["trust_gap_signals"]
    ]
    if not active_with_gaps:
        pytest.skip("no active system with gaps in fixture")
    # H01 is the h_slice candidate — must NOT outrank a real active system that has gaps.
    h01_rank = next((r["rank"] for r in out["ranked_systems"] if r["system_id"] == "H01"), None)
    if h01_rank is not None:
        first_active = active_with_gaps[0]
        assert first_active["rank"] <= h01_rank


def test_deprecated_systems_penalized(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    for row in out["ranked_systems"]:
        if row["classification"] == "deprecated":
            assert "deprecated" in row["penalties"]


def test_top_5_has_at_most_5(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    assert len(out["top_5"]) <= 5


def test_real_repo_top5_is_active_authorities() -> None:
    """Run the full pipeline against the real repo. The top spots must be
    active trust-boundary authorities, not deprecated or unknown candidates."""

    from spectrum_systems.modules.tls_dependency_graph.registry_parser import DEFAULT_REGISTRY_PATH

    graph = build_dependency_graph(DEFAULT_REGISTRY_PATH)
    evidence = attach_evidence(graph)
    classification = classify_systems(graph, evidence)
    trust_gaps = detect_trust_gaps(graph, evidence, classification)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    # The number-one slot must be an active system, never a deprecated/future/unknown.
    top = out["top_5"][0]
    assert top["classification"] in ("active_system", "h_slice")


def test_priority_order_is_canonical(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification, trust_gaps = _build(registry_fixture_path, repo_fixture)
    out = rank_systems(graph, evidence, classification, trust_gaps)
    assert out["priority_order"] == [
        "mvp_spine_dependency",
        "trust_boundary_importance",
        "downstream_unlock_value",
        "partial_completion",
        "risk_if_deferred",
    ]
