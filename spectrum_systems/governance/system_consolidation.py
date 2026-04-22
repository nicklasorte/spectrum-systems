"""Phase 5.2: System Consolidation

Merge adjacent systems with no dependency conflicts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


class SystemConsolidation:
    """Identify and plan merges for systems with zero dependency overlap."""

    def __init__(self, dependency_graph: Dict[str, Set[str]]) -> None:
        self.dependencies = {k: set(v) for k, v in dependency_graph.items()}

    def find_consolidation_candidates(self) -> List[Tuple[str, str]]:
        """Find pairs of systems that can be merged (no mutual dependency)."""
        candidates: List[Tuple[str, str]] = []
        systems = sorted(self.dependencies.keys())

        for i, sys1 in enumerate(systems):
            for sys2 in systems[i + 1:]:
                deps1 = self.dependencies.get(sys1, set())
                deps2 = self.dependencies.get(sys2, set())
                # Neither depends on the other
                if sys2 not in deps1 and sys1 not in deps2:
                    candidates.append((sys1, sys2))

        return candidates

    def plan_consolidation(self, sys1: str, sys2: str) -> Dict[str, Any]:
        """Plan how to merge sys2 into sys1."""
        return {
            "merge_from": sys2,
            "merge_into": sys1,
            "actions": [
                f"Move {sys2} owned_paths into {sys1}",
                f"Merge {sys2} schemas into {sys1}",
                f"Update all imports ({sys2} → {sys1})",
                f"Merge {sys2} tests into {sys1}",
                "Run consolidated tests",
            ],
        }
