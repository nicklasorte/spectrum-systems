"""Build and query artifact lineage graph."""

from dataclasses import dataclass
from typing import Dict, List, Set, Any, Optional


@dataclass
class LineageEdge:
    """Single lineage relationship."""
    parent_id: str
    parent_type: str
    child_id: str
    child_type: str
    relation_type: str
    timestamp: str
    schema_version: str = "1.0"


class LineageGraph:
    """Directed acyclic graph of artifact dependencies."""

    def __init__(self):
        self.edges: List[LineageEdge] = []
        self.adjacency: Dict[str, Set[str]] = {}

    def add_edge(self, edge: LineageEdge) -> None:
        """Add edge to graph."""
        self.edges.append(edge)

        if edge.parent_id not in self.adjacency:
            self.adjacency[edge.parent_id] = set()
        self.adjacency[edge.parent_id].add(edge.child_id)

    def get_upstream(self, artifact_id: str, depth: int = 10) -> Set[str]:
        """Find all artifacts that led to this one."""
        upstream = set()
        queue = [artifact_id]
        visited = set()

        while queue and depth > 0:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            for edge in self.edges:
                if edge.child_id == current and edge.parent_id not in visited:
                    upstream.add(edge.parent_id)
                    queue.append(edge.parent_id)

            depth -= 1

        return upstream

    def get_downstream(self, artifact_id: str, depth: int = 10) -> Set[str]:
        """Find all artifacts that depend on this one."""
        downstream = set()
        for child_id in self.adjacency.get(artifact_id, set()):
            downstream.add(child_id)
            downstream |= self.get_downstream(child_id, depth - 1)
        return downstream

    def explain_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """Explain why this artifact exists."""
        upstream = self.get_upstream(artifact_id)
        downstream = self.get_downstream(artifact_id)

        return {
            'artifact_id': artifact_id,
            'created_from': list(upstream),
            'used_by': list(downstream),
            'explanation': self._generate_explanation(artifact_id, upstream)
        }

    def _generate_explanation(self, artifact_id: str, upstream: Set[str]) -> str:
        """Natural language explanation of artifact origin."""
        if 'policy' in artifact_id:
            return f'Policy created from {len(upstream)} eval cases'
        elif 'eval' in artifact_id:
            return f'Eval case created from {len(upstream)} incidents'
        else:
            return f'Artifact created from {len(upstream)} sources'
