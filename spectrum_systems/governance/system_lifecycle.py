"""System lifecycle state management with immutable audit trail.

Valid states: active, superseded, frozen, deprecated.
All transitions are logged. Non-active systems cannot execute.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

VALID_STATES = frozenset({"active", "superseded", "frozen", "deprecated"})

_VALID_TRANSITIONS: Dict[str, frozenset] = {
    "active": frozenset({"superseded", "frozen", "deprecated"}),
    "superseded": frozenset({"deprecated"}),
    "frozen": frozenset({"deprecated"}),
    "deprecated": frozenset(),
}

_STATES_THAT_BLOCK_EXECUTION = frozenset({"superseded", "frozen", "deprecated"})


class SystemLifecycle:
    """Manages lifecycle state for registered systems.

    State is held in memory with an append-only audit trail.
    Systems start as active unless initialized otherwise.
    """

    def __init__(self) -> None:
        self._state: Dict[str, str] = {}
        self._audit_trail: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def register(self, system_id: str, initial_state: str = "active") -> None:
        """Register a system. Raises if already registered or state invalid."""
        if system_id in self._state:
            raise ValueError(f"System '{system_id}' already registered")
        if initial_state not in VALID_STATES:
            raise ValueError(f"Invalid initial state '{initial_state}'")
        self._state[system_id] = initial_state
        self._audit_trail[system_id] = []
        self._record_transition(system_id, prior=None, current=initial_state, reason="initial_registration", metadata={})

    def supersede(self, system_id: str, reason: str, superseded_by: str) -> Dict:
        """Transition system to superseded. Returns the supersession record."""
        return self._transition(
            system_id,
            target="superseded",
            reason=reason,
            metadata={"superseded_by": superseded_by},
            record_type="system_supersession_record",
        )

    def freeze(self, system_id: str, reason: str) -> Dict:
        """Transition system to frozen. Returns the freeze record."""
        return self._transition(
            system_id,
            target="frozen",
            reason=reason,
            metadata={},
            record_type="system_freeze_record",
        )

    def deprecate(self, system_id: str, reason: str) -> Dict:
        """Transition system to deprecated."""
        return self._transition(
            system_id,
            target="deprecated",
            reason=reason,
            metadata={},
            record_type="system_deprecation_record",
        )

    def activate(self, system_id: str, reason: str = "reactivation") -> Dict:
        """Re-activate a system from frozen state only (frozen → active)."""
        self._ensure_registered(system_id)
        current = self._state[system_id]
        if current != "frozen":
            raise ValueError(f"Cannot reactivate system in state '{current}' (only frozen→active allowed)")
        self._state[system_id] = "active"
        entry = self._record_transition(system_id, prior=current, current="active", reason=reason, metadata={})
        return entry

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_active(self, system_id: str) -> bool:
        """Return True only if system status is 'active'."""
        self._ensure_registered(system_id)
        return self._state[system_id] == "active"

    def get_status(self, system_id: str) -> str:
        self._ensure_registered(system_id)
        return self._state[system_id]

    def get_audit_trail(self, system_id: str) -> List[Dict]:
        """Return immutable copy of the audit trail for a system."""
        self._ensure_registered(system_id)
        return list(self._audit_trail[system_id])

    def check_execution_allowed(self, system_id: str) -> Tuple[bool, str]:
        """Gate: return (allowed, reason). Non-active systems are blocked."""
        self._ensure_registered(system_id)
        status = self._state[system_id]
        if status in _STATES_THAT_BLOCK_EXECUTION:
            return False, f"System '{system_id}' is '{status}' — execution blocked"
        return True, "active"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(
        self,
        system_id: str,
        target: str,
        reason: str,
        metadata: Dict,
        record_type: str,
    ) -> Dict:
        self._ensure_registered(system_id)
        current = self._state[system_id]
        allowed = _VALID_TRANSITIONS.get(current, frozenset())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition '{current}' → '{target}' for system '{system_id}'. "
                f"Allowed: {sorted(allowed) or 'none'}"
            )
        self._state[system_id] = target
        return self._record_transition(
            system_id, prior=current, current=target, reason=reason, metadata={**metadata, "record_type": record_type}
        )

    def _record_transition(
        self,
        system_id: str,
        prior: Optional[str],
        current: str,
        reason: str,
        metadata: Dict,
    ) -> Dict:
        entry = {
            "record_id": f"LC-{uuid.uuid4().hex[:12].upper()}",
            "system_id": system_id,
            "prior_state": prior,
            "current_state": current,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metadata,
        }
        self._audit_trail[system_id].append(entry)
        return entry

    def _ensure_registered(self, system_id: str) -> None:
        if system_id not in self._state:
            raise KeyError(f"System '{system_id}' not registered")
