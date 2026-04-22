"""Phase 5.3: Responsibility Matrix

Define clear, non-overlapping ownership boundaries.
Raises on duplicate assignment to enforce hard separation.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple


class ResponsibilityMatrix:
    """Track and enforce non-overlapping system responsibilities."""

    def __init__(self) -> None:
        # responsibility → owning system
        self._responsibilities: Dict[str, str] = {}
        # system → set of responsibilities
        self._system_owns: Dict[str, Set[str]] = {}

    def assign_responsibility(self, responsibility: str, system_id: str) -> None:
        """Assign a responsibility to a system. Raises if already owned."""
        if responsibility in self._responsibilities:
            existing_owner = self._responsibilities[responsibility]
            raise ValueError(
                f"Responsibility '{responsibility}' already owned by "
                f"'{existing_owner}'; cannot assign to '{system_id}'."
            )
        self._responsibilities[responsibility] = system_id
        self._system_owns.setdefault(system_id, set()).add(responsibility)

    def get_owner(self, responsibility: str) -> str:
        """Return the system that owns a responsibility."""
        if responsibility not in self._responsibilities:
            raise KeyError(f"Responsibility '{responsibility}' has no assigned owner.")
        return self._responsibilities[responsibility]

    def get_owned_by(self, system_id: str) -> Set[str]:
        """Return all responsibilities owned by a system."""
        return set(self._system_owns.get(system_id, set()))

    def validate_no_overlap(self) -> Tuple[bool, List[str]]:
        """Verify no responsibility is claimed by more than one system.

        The data model prevents overlap at assignment time, so this always
        returns (True, []). Kept as an explicit audit surface.
        """
        return True, []

    def audit(self) -> Dict[str, str]:
        """Return full responsibility → owner mapping for audit."""
        return dict(self._responsibilities)
