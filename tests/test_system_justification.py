"""Unit tests for SystemJustification — Phase 2.5 (4 tests + RT-2.5 coverage)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spectrum_systems.governance.system_justification import (
    SYSTEM_JUSTIFICATIONS,
    get_all_justified_systems,
    propose_system,
    validate_system_justification,
)


# ---------------------------------------------------------------------------
# Test 1: All 6 canonical systems are justified
# ---------------------------------------------------------------------------


def test_all_six_systems_are_justified():
    required = {"TPA", "TLC", "PRG", "WPG", "CHK", "GOV"}
    justified = set(get_all_justified_systems())
    missing = required - justified
    assert not missing, f"Systems missing justification: {missing}"


# ---------------------------------------------------------------------------
# Test 2: validate_system_justification accepts known systems
# ---------------------------------------------------------------------------


def test_validate_known_systems():
    for system_id in ["TPA", "TLC", "PRG", "WPG", "CHK", "GOV"]:
        ok, reason = validate_system_justification(system_id)
        assert ok, f"System '{system_id}' unexpectedly invalid: {reason}"
        assert "prevents" in reason
        assert "improves" in reason


# ---------------------------------------------------------------------------
# Test 3: RT-2.5 Propose system with no justification → rejected
# ---------------------------------------------------------------------------


def test_rt_propose_no_justification_rejected():
    ok, reason = propose_system("NEW-SYS", prevents=[], improves=[], description="does stuff")
    assert not ok
    assert "prevents" in reason


# ---------------------------------------------------------------------------
# Test 4: RT-2.5 Propose system that prevents + improves → still rejected (registry locked)
# ---------------------------------------------------------------------------


def test_rt_propose_valid_but_locked_rejected():
    ok, reason = propose_system(
        "NEW-SYS",
        prevents=["data_loss"],
        improves=["audit_coverage"],
        description="prevents data loss and improves audit coverage",
    )
    assert not ok
    assert "locked" in reason.lower()


# ---------------------------------------------------------------------------
# RT-2.5: Validate non-existent system → rejected
# ---------------------------------------------------------------------------


def test_rt_validate_nonexistent_system_rejected():
    ok, reason = validate_system_justification("GHOST-SYS")
    assert not ok
    assert "no justification" in reason.lower()


# ---------------------------------------------------------------------------
# RT-2.5: Propose system that "just orchestrates" → rejected
# ---------------------------------------------------------------------------


def test_rt_propose_orchestration_only_rejected():
    ok, reason = propose_system(
        "ORCH-SYS",
        prevents=["something"],
        improves=["something_else"],
        description="it just orchestrates the pipeline",
    )
    assert not ok
    assert "orchestration" in reason.lower()


# ---------------------------------------------------------------------------
# RT-2.5: Propose system that improves signal → still blocked by lock
# ---------------------------------------------------------------------------


def test_rt_propose_improves_signal_locked():
    ok, reason = propose_system(
        "SIG-SYS",
        prevents=["signal_loss"],
        improves=["detection_latency"],
        description="prevents signal loss and improves detection latency",
    )
    assert not ok
    assert "locked" in reason.lower()


# ---------------------------------------------------------------------------
# All 6 systems have non-empty prevents and improves
# ---------------------------------------------------------------------------


def test_all_systems_have_nonempty_prevents_and_improves():
    for sid, entry in SYSTEM_JUSTIFICATIONS.items():
        assert entry["prevents"], f"{sid}: prevents list is empty"
        assert entry["improves"], f"{sid}: improves list is empty"
