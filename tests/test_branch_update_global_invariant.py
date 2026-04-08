from __future__ import annotations

from spectrum_systems.modules.runtime.github_closure_continuation import resolve_terminal_state_policy


_TERMINAL_STATES = [
    "ready_for_merge",
    "blocked",
    "escalated",
    "exhausted",
    "malformed_input",
    "unknown_failure",
]


def test_branch_update_allowed_global_invariant() -> None:
    for terminal_state in _TERMINAL_STATES:
        policy = resolve_terminal_state_policy(terminal_state)
        assert policy["branch_update_allowed"] == (terminal_state == "ready_for_merge")
