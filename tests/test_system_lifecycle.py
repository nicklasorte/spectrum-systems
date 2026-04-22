"""Unit tests for SystemLifecycle — Phase 2.2 (8 tests + RT-2.2 coverage)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spectrum_systems.governance.system_lifecycle import SystemLifecycle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lc():
    mgr = SystemLifecycle()
    mgr.register("SYS-A")
    return mgr


# ---------------------------------------------------------------------------
# Test 1: Registered system starts as active
# ---------------------------------------------------------------------------


def test_registered_system_is_active(lc):
    assert lc.is_active("SYS-A")
    assert lc.get_status("SYS-A") == "active"


# ---------------------------------------------------------------------------
# Test 2: Superseded system is blocked from execution
# ---------------------------------------------------------------------------


def test_superseded_system_blocked(lc):
    lc.supersede("SYS-A", reason="replaced by SYS-B", superseded_by="SYS-B")
    allowed, msg = lc.check_execution_allowed("SYS-A")
    assert not allowed
    assert "superseded" in msg


# ---------------------------------------------------------------------------
# Test 3: Frozen system is blocked from execution
# ---------------------------------------------------------------------------


def test_frozen_system_blocked(lc):
    lc.freeze("SYS-A", reason="security review in progress")
    allowed, msg = lc.check_execution_allowed("SYS-A")
    assert not allowed
    assert "frozen" in msg


# ---------------------------------------------------------------------------
# Test 4: Deprecated system is blocked from execution
# ---------------------------------------------------------------------------


def test_deprecated_system_blocked():
    mgr = SystemLifecycle()
    mgr.register("SYS-D")
    mgr.deprecate("SYS-D", reason="end of life")
    allowed, msg = mgr.check_execution_allowed("SYS-D")
    assert not allowed
    assert "deprecated" in msg


# ---------------------------------------------------------------------------
# Test 5: Audit trail is immutable (modification raises)
# ---------------------------------------------------------------------------


def test_audit_trail_is_immutable(lc):
    lc.supersede("SYS-A", reason="replaced", superseded_by="SYS-B")
    trail = lc.get_audit_trail("SYS-A")
    assert isinstance(trail, list)
    trail.append({"evil": "entry"})
    clean_trail = lc.get_audit_trail("SYS-A")
    assert not any(e.get("evil") for e in clean_trail), "Audit trail was mutated externally"


# ---------------------------------------------------------------------------
# Test 6: Invalid state transition is rejected
# ---------------------------------------------------------------------------


def test_invalid_state_transition_rejected():
    mgr = SystemLifecycle()
    mgr.register("SYS-X")
    mgr.supersede("SYS-X", reason="replaced", superseded_by="SYS-Y")
    with pytest.raises(ValueError, match="Invalid transition"):
        mgr.freeze("SYS-X", reason="attempt to freeze superseded system")


# ---------------------------------------------------------------------------
# Test 7: State transitions are timestamped in audit trail
# ---------------------------------------------------------------------------


def test_transitions_have_timestamps(lc):
    lc.supersede("SYS-A", reason="ts test", superseded_by="SYS-B")
    trail = lc.get_audit_trail("SYS-A")
    for entry in trail:
        assert "timestamp" in entry
        assert entry["timestamp"]  # non-empty


# ---------------------------------------------------------------------------
# Test 8: Unregistered system raises KeyError on query
# ---------------------------------------------------------------------------


def test_unregistered_system_raises():
    mgr = SystemLifecycle()
    with pytest.raises(KeyError, match="not registered"):
        mgr.is_active("NO-SUCH-SYSTEM")


# ---------------------------------------------------------------------------
# RT-2.2: Supersede then attempt execute → blocked
# ---------------------------------------------------------------------------


def test_rt_supersede_blocks_execution():
    mgr = SystemLifecycle()
    mgr.register("GOV")
    mgr.supersede("GOV", reason="new version", superseded_by="GOV-V2")
    allowed, _ = mgr.check_execution_allowed("GOV")
    assert not allowed


# ---------------------------------------------------------------------------
# RT-2.2: Active system passes execution gate
# ---------------------------------------------------------------------------


def test_rt_active_system_allowed():
    mgr = SystemLifecycle()
    mgr.register("TLC")
    allowed, reason = mgr.check_execution_allowed("TLC")
    assert allowed
    assert reason == "active"


# ---------------------------------------------------------------------------
# RT-2.2: Frozen → reactivate → active
# ---------------------------------------------------------------------------


def test_rt_frozen_can_be_reactivated():
    mgr = SystemLifecycle()
    mgr.register("PRG")
    mgr.freeze("PRG", reason="review")
    mgr.activate("PRG", reason="review complete")
    assert mgr.is_active("PRG")
    allowed, _ = mgr.check_execution_allowed("PRG")
    assert allowed
