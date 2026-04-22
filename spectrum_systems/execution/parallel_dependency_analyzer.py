"""Phase 3.0B: Parallel Execution Dependency Analysis

Build dependency graph: identify which slices can parallelize safely.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


class ParallelDependencyAnalyzer:
    """Analyze which slices can execute in parallel."""

    def __init__(self) -> None:
        self.dependencies: Dict[str, Set[str]] = {}

    def add_dependency(self, slice_id: str, depends_on: Set[str]) -> None:
        """Register dependencies for a slice."""
        self.dependencies[slice_id] = set(depends_on)

    def analyze_parallelization(self, slice_ids: List[str]) -> Dict[str, bool]:
        """Determine which slices can run in parallel (no unresolved deps)."""
        return {
            slice_id: len(self.dependencies.get(slice_id, set())) == 0
            for slice_id in slice_ids
        }

    def build_dependency_graph(self) -> Dict[str, Any]:
        """Build complete dependency graph artifact."""
        return {
            "artifact_type": "parallel_dependency_graph",
            "dependencies": {
                slice_id: list(deps)
                for slice_id, deps in self.dependencies.items()
            },
            "can_parallelize": self.analyze_parallelization(
                list(self.dependencies.keys())
            ),
        }
