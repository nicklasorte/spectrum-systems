"""Tests for RGE Loop Contribution Checker (Principle 2)."""
from __future__ import annotations

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.loop_contribution_checker import (
    CANONICAL_LOOP_LEGS,
    MAX_SYSTEMS_PER_LEG,
    LoopContributionError,
    check_loop_contribution,
)

_RUN = "run-lcc-001"
_TRACE = "trace-lcc-001"


def _phase(**overrides) -> dict:
    base = {"phase_id": "P2", "name": "Add EVL contributor", "loop_leg": "EVL"}
    return {**base, **overrides}


def test_valid_leg_healthy_returns_allow():
    r = check_loop_contribution(_phase(), run_id=_RUN, trace_id=_TRACE)
    assert r["decision"] == "allow"
    assert r["errors"] == []
    assert r["warnings"] == []


def test_drift_leg_blocks():
    with pytest.raises(LoopContributionError, match="active drift"):
        check_loop_contribution(
            _phase(), run_id=_RUN, trace_id=_TRACE, active_drift_legs=["EVL"]
        )


def test_saturated_leg_blocks():
    with pytest.raises(LoopContributionError, match="saturated"):
        check_loop_contribution(
            _phase(),
            run_id=_RUN,
            trace_id=_TRACE,
            current_leg_counts={"EVL": MAX_SYSTEMS_PER_LEG},
        )


def test_near_saturation_warns_but_allows():
    r = check_loop_contribution(
        _phase(),
        run_id=_RUN,
        trace_id=_TRACE,
        current_leg_counts={"EVL": MAX_SYSTEMS_PER_LEG - 2},
    )
    assert r["decision"] == "allow"
    assert r["warnings"]
    assert "approaching saturation" in r["warnings"][0]


def test_non_canonical_leg_blocks():
    with pytest.raises(LoopContributionError, match="not a canonical loop leg"):
        check_loop_contribution(_phase(loop_leg="MAGIC"), run_id=_RUN, trace_id=_TRACE)


def test_all_canonical_legs_accepted_when_healthy():
    for leg in CANONICAL_LOOP_LEGS:
        r = check_loop_contribution(_phase(loop_leg=leg), run_id=_RUN, trace_id=_TRACE)
        assert r["decision"] == "allow"


def test_deletion_phase_skips_saturation():
    r = check_loop_contribution(
        _phase(phase_type="delete"),
        run_id=_RUN,
        trace_id=_TRACE,
        current_leg_counts={"EVL": MAX_SYSTEMS_PER_LEG},
    )
    assert r["decision"] == "allow"


def test_empty_drift_and_counts():
    r = check_loop_contribution(
        _phase(), run_id=_RUN, trace_id=_TRACE,
        active_drift_legs=[], current_leg_counts={},
    )
    assert r["decision"] == "allow"


def test_warnings_populated_at_count_six():
    r = check_loop_contribution(
        _phase(),
        run_id=_RUN,
        trace_id=_TRACE,
        current_leg_counts={"EVL": 6},
    )
    assert r["decision"] == "allow"
    assert len(r["warnings"]) == 1


def test_record_principle_field():
    r = check_loop_contribution(_phase(), run_id=_RUN, trace_id=_TRACE)
    assert r["principle"] == "build_fewer_stronger_loops"


def test_stable_record_id_for_same_inputs():
    r1 = check_loop_contribution(_phase(), run_id=_RUN, trace_id=_TRACE)
    r2 = check_loop_contribution(_phase(), run_id=_RUN, trace_id=_TRACE)
    assert r1["record_id"] == r2["record_id"]


def test_schema_validates():
    r = check_loop_contribution(_phase(), run_id=_RUN, trace_id=_TRACE)
    validate_artifact(r, "loop_contribution_record")


def test_strengthen_phase_allowed_on_drift_leg():
    r = check_loop_contribution(
        _phase(phase_type="strengthen", name="STRENGTHEN-EVL add telemetry"),
        run_id=_RUN,
        trace_id=_TRACE,
        active_drift_legs=["EVL"],
    )
    assert r["decision"] == "allow"
