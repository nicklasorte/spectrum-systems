from __future__ import annotations

from spectrum_systems.modules.runtime.github_closure_continuation import resolve_terminal_state_policy


_REQUIRED_STATES = {
    "ready_for_merge": {"promotion_allowed": True, "branch_update_allowed": True, "cde_decision_path": "lock"},
    "blocked": {"promotion_allowed": False, "branch_update_allowed": False, "cde_decision_path": "blocked"},
    "escalated": {"promotion_allowed": False, "branch_update_allowed": False, "cde_decision_path": "escalate"},
    "exhausted": {"promotion_allowed": False, "branch_update_allowed": False, "cde_decision_path": "continue_bounded"},
    "malformed_input": {"promotion_allowed": False, "branch_update_allowed": False, "cde_decision_path": "blocked"},
    "unknown_failure": {"promotion_allowed": False, "branch_update_allowed": False, "cde_decision_path": "escalate"},
}


def test_all_required_terminal_states_have_explicit_policy() -> None:
    for terminal_state, expected in _REQUIRED_STATES.items():
        policy = resolve_terminal_state_policy(terminal_state)
        assert policy["terminal_state"] == terminal_state
        assert policy["promotion_allowed"] is expected["promotion_allowed"]
        assert policy["branch_update_allowed"] is expected["branch_update_allowed"]
        assert policy["cde_decision_path"] == expected["cde_decision_path"]
