"""Phase 5.1: System Elimination

Remove systems without justification (no prevents/improves).
"""

from __future__ import annotations

from typing import Any, Dict, List


class SystemElimination:
    """Manage system elimination process."""

    def __init__(self, system_justifications: Dict[str, Dict[str, Any]]) -> None:
        self.justifications = system_justifications

    def identify_unjustified_systems(self) -> List[str]:
        """Find systems with neither prevents nor improves entries."""
        unjustified = []
        for system_id, justif in self.justifications.items():
            if not justif.get("prevents") and not justif.get("improves"):
                unjustified.append(system_id)
        return sorted(unjustified)

    def plan_elimination(self, system_id: str) -> Dict[str, Any]:
        """Return ordered steps to safely eliminate a system."""
        return {
            "system_id": system_id,
            "actions": [
                f"Delete {system_id} module files",
                f"Delete {system_id} tests",
                f"Delete {system_id} schemas",
                f"Update imports in dependent systems",
                "Run regression tests",
            ],
        }

    def validate_no_orphaned_dependencies(
        self, system_id: str, dependency_graph: Dict[str, List[str]]
    ) -> bool:
        """Return True when no other system depends on system_id."""
        for sys_id, deps in dependency_graph.items():
            if sys_id != system_id and system_id in deps:
                return False
        return True
