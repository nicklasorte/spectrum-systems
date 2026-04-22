"""Tests for Phase 3.0B: ParallelDependencyAnalyzer."""

import pytest

from spectrum_systems.execution.parallel_dependency_analyzer import (
    ParallelDependencyAnalyzer,
)


@pytest.fixture()
def analyzer():
    return ParallelDependencyAnalyzer()


# ---------------------------------------------------------------------------
# test_no_dependencies_can_parallelize
# ---------------------------------------------------------------------------
def test_no_dependencies_can_parallelize(analyzer):
    analyzer.add_dependency("slice-A", set())
    analyzer.add_dependency("slice-B", set())
    result = analyzer.analyze_parallelization(["slice-A", "slice-B"])
    assert result["slice-A"] is True
    assert result["slice-B"] is True


# ---------------------------------------------------------------------------
# test_with_dependencies_cannot_parallelize
# ---------------------------------------------------------------------------
def test_with_dependencies_cannot_parallelize(analyzer):
    analyzer.add_dependency("slice-A", set())
    analyzer.add_dependency("slice-B", {"slice-A"})  # B depends on A
    result = analyzer.analyze_parallelization(["slice-A", "slice-B"])
    assert result["slice-A"] is True
    assert result["slice-B"] is False


# ---------------------------------------------------------------------------
# test_dependency_graph_built
# ---------------------------------------------------------------------------
def test_dependency_graph_built(analyzer):
    analyzer.add_dependency("slice-A", set())
    analyzer.add_dependency("slice-B", {"slice-A"})
    graph = analyzer.build_dependency_graph()
    assert graph["artifact_type"] == "parallel_dependency_graph"
    assert "slice-A" in graph["dependencies"]
    assert "slice-B" in graph["dependencies"]
    assert graph["can_parallelize"]["slice-A"] is True
    assert graph["can_parallelize"]["slice-B"] is False
