"""System dependency map for the 3LS simplification audit (Phase 1.1).

Maps system-to-system call relationships and identifies what breaks
if a system is removed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple


# Canonical dependency graph: system → set of systems it depends on
CANONICAL_DEPENDENCY_GRAPH: Dict[str, Set[str]] = {
    "AEX": {"TLC"},
    "TLC": {"PQX", "TPA", "FRE", "RIL", "RQX", "CDE", "PRG"},
    "TPA": {"PQX", "GOV"},
    "PRG": {"TLC", "CDE"},
    "WPG": {"TLC", "PQX"},
    "CHK": {"TLC", "PQX"},
    "GOV": {"TLC", "CDE", "SEL"},
    "PQX": set(),
    "CDE": set(),
    "SEL": set(),
    "FRE": set(),
    "RIL": {"CDE"},
    "RQX": {"RIL", "FRE", "TPA"},
    # Phase 2 consolidated systems
    "GOVERN": {"PQX", "CDE", "SEL"},
    "EXEC": {"GOVERN", "PQX"},
    "EVAL": {"GOVERN", "EXEC", "PQX"},
}


class SystemDependencyMap:
    """Map system-to-system calls and analyze removal impact."""

    def __init__(
        self,
        dependency_graph: Optional[Dict[str, Any]] = None,
    ) -> None:
        if dependency_graph is not None:
            self.dependencies: Dict[str, Set[str]] = {
                k: set(v) for k, v in dependency_graph.items()
            }
        else:
            self.dependencies = {k: set(v) for k, v in CANONICAL_DEPENDENCY_GRAPH.items()}

    def add_dependency(self, caller: str, callee: str, interaction_type: str = "calls") -> None:
        """Register that caller depends on callee for interaction_type."""
        self.dependencies.setdefault(caller, set()).add(callee)

    def get_dependent_systems(self, system_id: str) -> List[str]:
        """Return systems that would break if system_id were removed."""
        dependents = []
        for sys_id, deps in self.dependencies.items():
            if sys_id != system_id and system_id in deps:
                dependents.append(sys_id)
        return sorted(dependents)

    def get_dependencies_of(self, system_id: str) -> List[str]:
        """Return systems that system_id depends on."""
        return sorted(self.dependencies.get(system_id, set()))

    def find_consolidation_candidates(self) -> List[Tuple[str, str]]:
        """Return pairs of systems with no mutual dependency — safe to merge."""
        candidates: List[Tuple[str, str]] = []
        systems = sorted(self.dependencies.keys())
        for i, sys1 in enumerate(systems):
            for sys2 in systems[i + 1:]:
                deps1 = self.dependencies.get(sys1, set())
                deps2 = self.dependencies.get(sys2, set())
                if sys2 not in deps1 and sys1 not in deps2:
                    candidates.append((sys1, sys2))
        return candidates

    def removal_impact(self, system_id: str) -> Dict[str, Any]:
        """Summarize what breaks if system_id is removed."""
        dependents = self.get_dependent_systems(system_id)
        return {
            "system_id": system_id,
            "dependent_systems": dependents,
            "safe_to_remove": len(dependents) == 0,
            "impact_summary": (
                f"Removing {system_id} breaks: {dependents}" if dependents
                else f"No dependents found for {system_id}"
            ),
        }

    def visualize(self) -> str:
        """Return a text call-matrix showing all dependencies."""
        lines = ["System Dependency Matrix", "=" * 40]
        for sys_id in sorted(self.dependencies.keys()):
            deps = sorted(self.dependencies[sys_id])
            dependents = self.get_dependent_systems(sys_id)
            lines.append(f"{sys_id}")
            if deps:
                lines.append(f"  depends_on: {', '.join(deps)}")
            if dependents:
                lines.append(f"  depended_by: {', '.join(dependents)}")
        return "\n".join(lines)
