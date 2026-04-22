"""Tests for Phase 4.3: LineageGraph."""

import pytest

from spectrum_systems.tracing.lineage_graph import LineageGraph


@pytest.fixture()
def graph():
    return LineageGraph()


def _build_simple_chain(graph: LineageGraph) -> None:
    """input-1 → exec-1 → output-1."""
    graph.add_artifact("input-1", "input_artifact", {"source": "user"})
    graph.add_artifact("exec-1", "execution_artifact", {})
    graph.add_artifact("output-1", "output_artifact", {})
    graph.add_lineage_edge("input-1", "exec-1")
    graph.add_lineage_edge("exec-1", "output-1")


# ---------------------------------------------------------------------------
# test_lineage_path_complete
# ---------------------------------------------------------------------------
def test_lineage_path_complete(graph):
    _build_simple_chain(graph)
    path = graph.get_lineage_path("output-1")
    assert "input-1" in path
    assert "exec-1" in path
    assert "output-1" in path


# ---------------------------------------------------------------------------
# test_orphaned_artifacts_detected
# ---------------------------------------------------------------------------
def test_orphaned_artifacts_detected(graph):
    graph.add_artifact("orphan-1", "output_artifact", {})
    ok, report = graph.validate_lineage_complete("orphan-1")
    assert ok is False
    assert "No input artifact" in report["reason"]


# ---------------------------------------------------------------------------
# test_query_produced_by
# ---------------------------------------------------------------------------
def test_query_produced_by(graph):
    _build_simple_chain(graph)
    produced = graph.query_produced_by("input-1")
    assert "exec-1" in produced
    assert "output-1" in produced


# ---------------------------------------------------------------------------
# test_query_produces
# ---------------------------------------------------------------------------
def test_query_produces(graph):
    _build_simple_chain(graph)
    sources = graph.query_produces("output-1")
    assert "input-1" in sources
    assert "exec-1" in sources


# ---------------------------------------------------------------------------
# test_validate_lineage_complete_deep_chain
# ---------------------------------------------------------------------------
def test_validate_lineage_complete_deep_chain(graph):
    for i in range(5):
        graph.add_artifact(f"node-{i}", "artifact", {})
        if i > 0:
            graph.add_lineage_edge(f"node-{i-1}", f"node-{i}")
    ok, report = graph.validate_lineage_complete("node-4")
    assert ok is True
    assert report["lineage_depth"] == 4
