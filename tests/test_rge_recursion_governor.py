"""Tests for RGE Recursion Governor."""
from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.recursion_governor import (
    MAX_RECURSION_DEPTH,
    RECURSION_BUDGET_PER_WEEK,
    govern_recursion,
)

_RUN = "run-rg-001"
_TRACE = "trace-rg-001"


def test_depth_zero_allowed():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="STRENGTHEN-EVL telemetry",
        current_depth=0,
    )
    assert r["decision"] == "allow"
    assert r["allowed"] is True
    validate_artifact(r, "rge_recursion_record")


def test_depth_at_max_allowed():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=MAX_RECURSION_DEPTH,
    )
    assert r["decision"] == "allow"


def test_depth_over_max_blocked():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=MAX_RECURSION_DEPTH + 1,
    )
    assert r["decision"] == "block_depth"
    assert r["allowed"] is False
    assert any("MAX_RECURSION_DEPTH" in reason for reason in r["block_reasons"])


def test_budget_exhausted_blocks():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=0,
        weekly_budget_used=RECURSION_BUDGET_PER_WEEK,
    )
    assert r["decision"] == "block_budget"


def test_circular_chain_blocked():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="STRENGTHEN EVL telemetry",
        current_depth=1,
        ancestor_phase_names=["STRENGTHEN EVL telemetry"],
    )
    assert r["decision"] == "block_cycle"


def test_different_signatures_not_blocked():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Delete legacy pubsub",
        current_depth=1,
        ancestor_phase_names=["STRENGTHEN EVL telemetry"],
    )
    assert r["decision"] == "allow"


def test_depth_priority_over_budget():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=MAX_RECURSION_DEPTH + 1,
        weekly_budget_used=RECURSION_BUDGET_PER_WEEK,
    )
    assert r["decision"] == "block_depth"


def test_audit_record_always_emitted():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=MAX_RECURSION_DEPTH + 5,
    )
    assert r["artifact_type"] == "rge_recursion_record"


def test_negative_depth_blocked():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=-1,
    )
    assert r["decision"] == "block_depth"


def test_schema_validates():
    r = govern_recursion(
        run_id=_RUN,
        trace_id=_TRACE,
        proposed_phase_name="Phase X",
        current_depth=0,
    )
    validate_artifact(r, "rge_recursion_record")
