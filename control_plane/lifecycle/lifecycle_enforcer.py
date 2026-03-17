"""
Lifecycle Enforcer — spectrum-systems control plane.

Validates artifact lifecycle state transitions against the canonical transition
table defined in ``lifecycle_transitions.json``.  Enforces required-field
presence before any state advance is allowed.

Usage (programmatic)::

    from control_plane.lifecycle.lifecycle_enforcer import LifecycleEnforcer

    enforcer = LifecycleEnforcer()
    enforcer.validate_transition(artifact, from_state="input", to_state="transformed")
    # raises LifecycleViolationError on failure

Usage (CLI)::

    python -m control_plane.lifecycle.lifecycle_enforcer \\
        --artifact artifact.json \\
        --from input --to transformed
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent


class LifecycleViolationError(Exception):
    """Raised when a requested lifecycle transition is invalid or blocked."""


class LifecycleEnforcer:
    """Central enforcement authority for artifact lifecycle transitions.

    Loads transition rules from ``lifecycle_transitions.json`` and state
    definitions from ``lifecycle_states.json`` at instantiation time.
    """

    def __init__(
        self,
        transitions_path: Optional[Path] = None,
        states_path: Optional[Path] = None,
    ) -> None:
        transitions_path = transitions_path or _HERE / "lifecycle_transitions.json"
        states_path = states_path or _HERE / "lifecycle_states.json"

        self._transitions: List[Dict[str, Any]] = json.loads(
            transitions_path.read_text(encoding="utf-8")
        )["transitions"]

        states_doc = json.loads(states_path.read_text(encoding="utf-8"))
        self._valid_states: set[str] = {s["state"] for s in states_doc["states"]}
        self._terminal_states: set[str] = {
            s["state"] for s in states_doc["states"] if s.get("terminal", False)
        }

        # Build a fast lookup: (from_state, to_state) → transition rule
        self._transition_map: Dict[tuple[str, str], Dict[str, Any]] = {
            (t["from"], t["to"]): t for t in self._transitions
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def valid_states(self) -> set[str]:
        """Return the set of all known lifecycle state names."""
        return set(self._valid_states)

    def validate_state(self, state: str) -> None:
        """Raise if *state* is not a recognised lifecycle state."""
        if state not in self._valid_states:
            raise LifecycleViolationError(
                f"Unknown lifecycle state '{state}'. "
                f"Valid states: {sorted(self._valid_states)}"
            )

    def validate_transition(
        self,
        artifact: Dict[str, Any],
        from_state: str,
        to_state: str,
    ) -> None:
        """Validate that the artifact may transition from *from_state* to *to_state*.

        Rules checked (in order):
        1. Both states must be recognised lifecycle states.
        2. The transition must appear in ``lifecycle_transitions.json``.
        3. All required fields for the transition must be present in *artifact*.

        Raises :class:`LifecycleViolationError` with a descriptive message on
        the first violation found.
        """
        # Rule 1 — known states
        self.validate_state(from_state)
        self.validate_state(to_state)

        # Rule 2 — transition must be defined
        rule = self._transition_map.get((from_state, to_state))
        if rule is None:
            allowed = [t["to"] for t in self._transitions if t["from"] == from_state]
            raise LifecycleViolationError(
                f"Invalid lifecycle transition: '{from_state}' → '{to_state}'. "
                f"Allowed next states from '{from_state}': {allowed or ['(none — terminal)']}"
            )

        # Rule 3 — required fields must be present in artifact
        missing = _check_required_fields(artifact, rule.get("required_fields", []))
        if missing:
            raise LifecycleViolationError(
                f"Transition '{from_state}' → '{to_state}' blocked: "
                f"artifact is missing required fields: {missing}. "
                f"Populate these fields before advancing the lifecycle state."
            )

    def allowed_next_states(self, from_state: str) -> List[str]:
        """Return the list of states reachable from *from_state*."""
        self.validate_state(from_state)
        return [t["to"] for t in self._transitions if t["from"] == from_state]

    def is_terminal(self, state: str) -> bool:
        """Return True if *state* is a terminal lifecycle state."""
        self.validate_state(state)
        return state in self._terminal_states


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _check_required_fields(
    artifact: Dict[str, Any],
    required_fields: List[str],
) -> List[str]:
    """Return the list of *required_fields* absent from *artifact*.

    A field is considered present when it exists as a key in *artifact* AND its
    value is not ``None`` or an empty string.  Boolean ``False`` counts as
    present.
    """
    missing = []
    for f in required_fields:
        if f not in artifact:
            missing.append(f)
            continue
        val = artifact[f]
        # None or empty string → missing; False is explicitly allowed (boolean field)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(f)
    return missing


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def _main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Validate an artifact lifecycle transition."
    )
    parser.add_argument("--artifact", required=True, help="Path to artifact JSON file.")
    parser.add_argument("--from", dest="from_state", required=True, help="Current lifecycle state.")
    parser.add_argument("--to", dest="to_state", required=True, help="Target lifecycle state.")
    args = parser.parse_args(argv)

    artifact_path = Path(args.artifact)
    if not artifact_path.is_file():
        print(f"ERROR: Artifact file not found: {artifact_path}", file=sys.stderr)
        return 1

    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Cannot load artifact: {exc}", file=sys.stderr)
        return 1

    enforcer = LifecycleEnforcer()
    try:
        enforcer.validate_transition(artifact, args.from_state, args.to_state)
        print(f"OK  Transition '{args.from_state}' → '{args.to_state}' is valid.")
        return 0
    except LifecycleViolationError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(_main())
