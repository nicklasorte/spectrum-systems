"""Tests for the RFX CDE→SEL decision-bridge guard (LOOP-04)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_decision_bridge_guard import (
    RFXDecisionBridgeGuardError,
    assert_rfx_cde_sel_decision_bridge,
)


_VALID_CDE = {
    "decision_id": "cde-rfx-001",
    "status": "ready",
    "cde_decision_id": "cde-rfx-001",
}

_VALID_SEL = {
    "sel_record_id": "sel-rfx-001",
    "cde_decision_ref": "cde-rfx-001",
    "enforcement_action": "allow",
}


# ---------------------------------------------------------------------------
# Missing CDE / invalid CDE
# ---------------------------------------------------------------------------

def test_missing_cde_decision_blocks_sel() -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=None, sel_context=_VALID_SEL)


def test_empty_cde_decision_blocks_sel() -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision={}, sel_context=_VALID_SEL)


def test_invalid_cde_status_blocks_sel() -> None:
    bad = {**_VALID_CDE, "status": "in_progress"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_invalid_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=bad, sel_context=_VALID_SEL)


def test_missing_cde_status_blocks_sel() -> None:
    bad = {"decision_id": "cde-rfx-001"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_invalid_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=bad, sel_context=_VALID_SEL)


def test_cde_decision_missing_id_blocks_sel() -> None:
    bad = {"status": "ready"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_invalid_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=bad, sel_context=_VALID_SEL)


# ---------------------------------------------------------------------------
# Missing SEL / SEL not linked
# ---------------------------------------------------------------------------

def test_missing_sel_context_blocks_bridge() -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_sel_context"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=_VALID_CDE, sel_context=None)


def test_empty_sel_context_blocks_bridge() -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_sel_context"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=_VALID_CDE, sel_context={})


def test_sel_without_cde_link_blocks_bridge() -> None:
    unlinked = {"sel_record_id": "sel-rfx-001", "enforcement_action": "allow"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=_VALID_CDE, sel_context=unlinked)


def test_sel_with_mismatched_cde_link_blocks_bridge() -> None:
    mismatch = {"sel_record_id": "sel-rfx-001", "cde_decision_ref": "cde-other-999"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=_VALID_CDE, sel_context=mismatch)


# ---------------------------------------------------------------------------
# Valid bridge
# ---------------------------------------------------------------------------

def test_valid_cde_sel_bridge_passes() -> None:
    # Must not raise
    assert_rfx_cde_sel_decision_bridge(cde_decision=_VALID_CDE, sel_context=_VALID_SEL)


def test_valid_not_ready_decision_with_linked_sel_passes() -> None:
    cde = {**_VALID_CDE, "status": "not_ready"}
    sel = {**_VALID_SEL, "enforcement_action": "block"}
    # Must not raise — "not_ready" is a valid CDE status; SEL still must link.
    assert_rfx_cde_sel_decision_bridge(cde_decision=cde, sel_context=sel)


def test_whitespace_padded_link_matches_after_trim() -> None:
    """LOOP-04 must trim both sides of the linkage comparison so that
    whitespace-padded values from upstream producers don't cause an
    avoidable fail-closed mismatch (LOOP-06 already strips both sides)."""
    cde = {"decision_id": " cde-rfx-001 ", "status": "ready"}
    sel = {"sel_record_id": "sel-rfx-001", "cde_decision_ref": "cde-rfx-001"}
    # Must not raise — the strip on both sides yields equal ids.
    assert_rfx_cde_sel_decision_bridge(cde_decision=cde, sel_context=sel)


def test_whitespace_padded_sel_link_matches_after_trim() -> None:
    cde = {"decision_id": "cde-rfx-001", "status": "ready"}
    sel = {"sel_record_id": "sel-rfx-001", "cde_decision_ref": "  cde-rfx-001\t"}
    # Must not raise.
    assert_rfx_cde_sel_decision_bridge(cde_decision=cde, sel_context=sel)


def test_whitespace_only_link_value_is_treated_as_absent() -> None:
    """A purely whitespace value still fails closed."""
    cde = {**_VALID_CDE}
    sel = {"sel_record_id": "sel-rfx-001", "cde_decision_ref": "   "}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=cde, sel_context=sel)
