"""Phase 4.3: Lineage Graph

Maintain complete lineage graph: input → execution → output.
Implemented with stdlib collections (no external graph libraries required).
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Set, Tuple


class LineageGraph:
    """Build and query complete lineage graph using adjacency lists."""

    def __init__(self) -> None:
        # node_id → metadata
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # source → {targets}
        self._edges: Dict[str, Set[str]] = {}
        # target → {sources}  (reverse index for ancestor queries)
        self._reverse_edges: Dict[str, Set[str]] = {}

    def add_artifact(
        self, artifact_id: str, artifact_type: str, metadata: Dict[str, Any]
    ) -> None:
        """Add artifact node to graph."""
        self._nodes[artifact_id] = {"type": artifact_type, **metadata}
        self._edges.setdefault(artifact_id, set())
        self._reverse_edges.setdefault(artifact_id, set())

    def add_lineage_edge(
        self,
        source_artifact_id: str,
        target_artifact_id: str,
        edge_type: str = "produces",
    ) -> None:
        """Add directed edge source → target."""
        self._edges.setdefault(source_artifact_id, set()).add(target_artifact_id)
        self._reverse_edges.setdefault(target_artifact_id, set()).add(source_artifact_id)
        # Ensure both nodes are in the graph
        self._nodes.setdefault(source_artifact_id, {})
        self._nodes.setdefault(target_artifact_id, {})
        self._edges.setdefault(target_artifact_id, set())
        self._reverse_edges.setdefault(source_artifact_id, set())

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------

    def _ancestors(self, artifact_id: str) -> Set[str]:
        """BFS over reverse edges to find all ancestors."""
        visited: Set[str] = set()
        queue = deque(self._reverse_edges.get(artifact_id, set()))
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(self._reverse_edges.get(node, set()) - visited)
        return visited

    def _descendants(self, artifact_id: str) -> Set[str]:
        """BFS over forward edges to find all descendants."""
        visited: Set[str] = set()
        queue = deque(self._edges.get(artifact_id, set()))
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(self._edges.get(node, set()) - visited)
        return visited

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_lineage_path(self, artifact_id: str) -> List[str]:
        """Return sorted list of all ancestors plus the artifact itself."""
        ancestors = self._ancestors(artifact_id)
        ancestors.add(artifact_id)
        return sorted(ancestors)

    def validate_lineage_complete(
        self, artifact_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Verify lineage chain is complete (artifact has at least one ancestor)."""
        if artifact_id not in self._nodes:
            return False, {"reason": "Artifact not in graph"}

        ancestors = self._ancestors(artifact_id)
        if not ancestors:
            return False, {
                "artifact_id": artifact_id,
                "complete": False,
                "reason": "No input artifact found",
            }

        return True, {
            "artifact_id": artifact_id,
            "complete": True,
            "lineage_depth": len(ancestors),
        }

    def query_produced_by(self, input_artifact_id: str) -> List[str]:
        """What outputs did this input produce?"""
        return sorted(self._descendants(input_artifact_id))

    def query_produces(self, output_artifact_id: str) -> List[str]:
        """What inputs produced this output?"""
        return sorted(self._ancestors(output_artifact_id))
