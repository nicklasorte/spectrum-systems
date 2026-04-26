"""Phase 0 (TLS-00) — registry parser + canonical loop extraction tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.tls_dependency_graph.registry_parser import (
    DEFAULT_REGISTRY_PATH,
    RegistryParseError,
    build_dependency_graph,
    parse_registry,
)


def test_parse_registry_extracts_canonical_loop_and_overlays(registry_fixture_path: Path) -> None:
    graph = parse_registry(registry_fixture_path)
    assert graph.canonical_loop == ["AEX", "PQX", "EVL"]
    assert graph.canonical_overlays == ["REP", "LIN"]


def test_parse_registry_collects_all_active_systems(registry_fixture_path: Path) -> None:
    graph = parse_registry(registry_fixture_path)
    assert set(graph.active_systems) == {"AEX", "PQX", "EVL", "REP", "LIN"}


def test_parse_registry_collects_dependencies_and_artifacts(registry_fixture_path: Path) -> None:
    graph = parse_registry(registry_fixture_path)
    pqx = graph.active_systems["PQX"]
    assert pqx.upstream == ["AEX"]
    assert pqx.downstream == ["EVL"]
    assert pqx.artifacts_owned == ["pqx_slice_execution_record"]
    evl = graph.active_systems["EVL"]
    assert "required_eval_coverage" in evl.artifacts_owned
    assert "eval_slice_summary" in evl.artifacts_owned


def test_parse_registry_raises_on_missing_canonical_loop(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        """# Registry\n## Active executable systems\n### AEX\n- **Status:** active\n""",
        encoding="utf-8",
    )
    with pytest.raises(RegistryParseError):
        parse_registry(bad)


def test_parse_registry_raises_on_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(RegistryParseError):
        parse_registry(empty)


def test_parse_registry_fails_when_loop_system_not_active(tmp_path: Path) -> None:
    text = """# Registry
## Canonical loop

`AEX → ZZZ`

`REP + LIN`

## Active executable systems

### AEX
- **Status:** active
- **Purpose:** test
- **Upstream Dependencies:** none
- **Downstream Dependencies:** PQX
"""
    p = tmp_path / "r.md"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(RegistryParseError):
        parse_registry(p)


def test_real_repo_registry_parses_clean() -> None:
    """The real repo registry must parse without raising."""

    graph = parse_registry(DEFAULT_REGISTRY_PATH)
    assert "AEX" in graph.active_systems
    assert "PQX" in graph.active_systems
    assert graph.canonical_loop[0] == "AEX"
    # The loop and overlays from the real registry are stable invariants.
    assert graph.canonical_overlays == ["REP", "LIN", "OBS", "SLO"]


def test_build_dependency_graph_returns_schema_shape(registry_fixture_path: Path) -> None:
    payload = build_dependency_graph(registry_fixture_path)
    assert payload["schema_version"] == "tls-00.v1"
    assert payload["phase"] == "TLS-00"
    assert payload["canonical_loop"] == ["AEX", "PQX", "EVL"]
    assert payload["canonical_overlays"] == ["REP", "LIN"]
    sids = [n["system_id"] for n in payload["active_systems"]]
    assert sids == sorted(sids)
    # Merged/demoted preserved
    merged_ids = [r["system_id"] for r in payload["merged_or_demoted"]]
    assert "SUP" in merged_ids
    assert "HNX" in merged_ids
