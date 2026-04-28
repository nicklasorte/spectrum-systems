"""CL-19 / CL-20 / CL-21: SEL action mapping contract, wrong-action red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_action_mapping import (
    ActionMappingError,
    REASON_MUTATION_WITHOUT_ALLOW,
    REASON_NOOP_ON_FREEZE,
    REASON_OK,
    REASON_PROMOTE_ON_BLOCK,
    REASON_REPAIR_WITHOUT_AUTH,
    REASON_RETRY_ON_POLICY_MISMATCH,
    REASON_UNKNOWN_DECISION_MAPPING,
    allowed_actions_for,
    load_action_mapping_policy,
    validate_action_for_decision,
)


# --- CL-19 contract -----------------------------------------------------


def test_cl19_policy_loads_and_has_canonical_pairs() -> None:
    p = load_action_mapping_policy()
    pairs = {(d["decision"], d["action"]) for d in p["decision_action_pairs"]}
    assert ("allow", "allow_continuation") in pairs
    assert ("block", "block_no_mutation") in pairs
    assert ("freeze", "freeze_hold") in pairs
    assert ("repair_required", "bounded_repair") in pairs


def test_cl19_allowed_actions_lookup() -> None:
    assert allowed_actions_for("allow") == ["allow_continuation"]
    assert allowed_actions_for("freeze") == ["freeze_hold"]
    assert allowed_actions_for("repair_required") == ["bounded_repair"]


@pytest.mark.parametrize(
    "decision,action",
    [
        ("allow", "allow_continuation"),
        ("block", "block_no_mutation"),
        ("freeze", "freeze_hold"),
        ("repair_required", "bounded_repair"),
    ],
)
def test_cl19_canonical_pairs_validate(decision: str, action: str) -> None:
    result = validate_action_for_decision(decision=decision, action=action)
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == REASON_OK


# --- CL-20 red team: forbidden patterns --------------------------------


def test_cl20_promote_on_block_blocks() -> None:
    result = validate_action_for_decision(decision="block", action="allow_continuation")
    assert not result["ok"]
    # Either ACTION_PROMOTE_ON_BLOCK or ACTION_MUTATION_WITHOUT_ALLOW —
    # both indicate the same drift pattern; the policy resolves to the
    # first matching forbidden pattern (promote_on_block).
    assert result["primary_reason"] in (
        REASON_PROMOTE_ON_BLOCK,
        REASON_MUTATION_WITHOUT_ALLOW,
    )


def test_cl20_noop_on_freeze_blocks() -> None:
    result = validate_action_for_decision(decision="freeze", action="allow_continuation")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_NOOP_ON_FREEZE


def test_cl20_retry_on_policy_mismatch_blocks() -> None:
    result = validate_action_for_decision(decision="block", action="bounded_repair")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_RETRY_ON_POLICY_MISMATCH


def test_cl20_repair_without_authorization_blocks() -> None:
    result = validate_action_for_decision(decision="allow", action="bounded_repair")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_REPAIR_WITHOUT_AUTH


def test_cl20_unknown_decision_blocks() -> None:
    result = validate_action_for_decision(decision="ship_it", action="allow_continuation")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_UNKNOWN_DECISION_MAPPING


def test_cl20_empty_decision_blocks() -> None:
    result = validate_action_for_decision(decision="", action="block_no_mutation")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_UNKNOWN_DECISION_MAPPING


def test_cl20_empty_action_blocks() -> None:
    result = validate_action_for_decision(decision="allow", action="")
    assert not result["ok"]


# --- CL-21 fix pass -----------------------------------------------------


def test_cl21_action_for_each_decision_consistent() -> None:
    # Sweep every canonical decision; ensure its allowed action validates
    # and at least one inconsistent action blocks. Establishes that the
    # fix pass holds across the full mapping.
    p = load_action_mapping_policy()
    for entry in p["decision_action_pairs"]:
        decision = entry["decision"]
        action = entry["action"]
        ok = validate_action_for_decision(decision=decision, action=action)
        assert ok["ok"], (decision, action, ok)

    # And one wrong combo blocks
    wrong = validate_action_for_decision(decision="freeze", action="bounded_repair")
    assert not wrong["ok"]
