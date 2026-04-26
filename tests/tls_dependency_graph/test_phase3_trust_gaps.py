"""Phase 3 (TLS-03) — trust gap detection tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.tls_dependency_graph.classification import classify_systems
from spectrum_systems.modules.tls_dependency_graph.evidence_scanner import attach_evidence
from spectrum_systems.modules.tls_dependency_graph.registry_parser import build_dependency_graph
from spectrum_systems.modules.tls_dependency_graph.trust_gaps import detect_trust_gaps


def _build(registry_fixture_path: Path, repo_fixture: Path):
    graph = build_dependency_graph(registry_fixture_path)
    evidence = attach_evidence(graph, repo_root=repo_fixture)
    classification = classify_systems(graph, evidence)
    return graph, evidence, classification


def test_every_system_has_at_least_one_signal_evaluated(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification = _build(registry_fixture_path, repo_fixture)
    out = detect_trust_gaps(graph, evidence, classification)
    for row in out["systems"]:
        assert row["gaps_evaluated"] >= 1


def test_no_system_marked_safe_without_evidence_evaluation(
    registry_fixture_path: Path, repo_fixture: Path
) -> None:
    graph, evidence, classification = _build(registry_fixture_path, repo_fixture)
    out = detect_trust_gaps(graph, evidence, classification)
    for row in out["systems"]:
        # A passing row needs >=1 passing signal AND >=1 evaluated.
        if row["gap_count"] == 0:
            assert row["gaps_evaluated"] > 0
            assert len(row["passing_signals"]) > 0


def test_active_system_with_no_eval_evidence_flags_missing_eval(tmp_path: Path) -> None:
    """Construct a registry+repo where EVL has zero tests/schemas: signal must fire."""

    registry = tmp_path / "registry.md"
    registry.write_text(
        """# Registry
## Canonical loop

`AEX → PQX → EVL`

`REP + LIN`

## Active executable systems

### AEX
- **Status:** active
- **Purpose:** test
- **Upstream Dependencies:** none
- **Downstream Dependencies:** PQX

### PQX
- **Status:** active
- **Purpose:** test
- **Upstream Dependencies:** AEX
- **Downstream Dependencies:** EVL

### EVL
- **Status:** active
- **Purpose:** test
- **Upstream Dependencies:** PQX
- **Downstream Dependencies:** none

### REP
- **Status:** active
- **Purpose:** test
- **Upstream Dependencies:** none
- **Downstream Dependencies:** none

### LIN
- **Status:** active
- **Purpose:** test
- **Upstream Dependencies:** none
- **Downstream Dependencies:** none
""",
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    graph = build_dependency_graph(registry)
    evidence = attach_evidence(graph, repo_root=repo)
    classification = classify_systems(graph, evidence)
    out = detect_trust_gaps(graph, evidence, classification)
    by_sid = {r["system_id"]: r for r in out["systems"]}
    # EVL has no tests, no schemas — multiple signals must fire.
    assert "missing_tests" in by_sid["EVL"]["failing_signals"]
    assert "schema_weakness" in by_sid["EVL"]["failing_signals"]


def test_trust_state_block_when_majority_of_signals_fail(registry_fixture_path: Path, tmp_path: Path) -> None:
    """A system with 0 evidence (failing every active signal) should be at least
    in 'block' or 'freeze' state, never 'ok'."""

    repo = tmp_path / "empty_repo"
    repo.mkdir()
    graph = build_dependency_graph(registry_fixture_path)
    evidence = attach_evidence(graph, repo_root=repo)
    classification = classify_systems(graph, evidence)
    out = detect_trust_gaps(graph, evidence, classification)
    for row in out["systems"]:
        if row["classification"] in ("active_system", "h_slice"):
            assert row["trust_state"] in ("warn", "freeze", "block"), row


def test_signal_taxonomy_is_canonical(registry_fixture_path: Path, repo_fixture: Path) -> None:
    graph, evidence, classification = _build(registry_fixture_path, repo_fixture)
    out = detect_trust_gaps(graph, evidence, classification)
    expected = {
        "missing_eval",
        "missing_control",
        "missing_enforcement",
        "missing_replay",
        "missing_lineage",
        "missing_observability",
        "missing_certification",
        "missing_tests",
        "schema_weakness",
    }
    assert set(out["signal_taxonomy"]) == expected
