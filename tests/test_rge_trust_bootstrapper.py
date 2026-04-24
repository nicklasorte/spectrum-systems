"""Tests for RGE Trust Bootstrapper."""
from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.trust_bootstrapper import (
    SHADOW_TO_WARN_GATED,
    WARN_GATED_TO_AUTO,
    assess_trust,
)

_RUN = "run-tr-001"
_TRACE = "trace-tr-001"


def test_starts_in_shadow_with_no_history():
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-1",
        confidence=0.8,
    )
    assert r["resolved_mode"] == "shadow"
    assert r["execute"] is False
    validate_artifact(r, "rge_trust_record")


def test_shadow_to_warn_gated_requires_adjudication():
    history = [{"outcome": "accept"}] * 10
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-2",
        confidence=0.9,
        decision_history=history,
        prior_mode="shadow",
    )
    assert r["desired_mode"] == "autonomous"
    assert r["resolved_mode"] == "shadow"
    assert r["transition_blocked"] is True


def test_shadow_to_warn_gated_with_full_adjudication():
    history = [{"outcome": "accept"}] * 5 + [{"outcome": "override"}] * 2
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-3",
        confidence=0.75,
        decision_history=history,
        prior_mode="shadow",
        adjudication_bundle={"cde_decision": "allow", "tpa_record": "TPA-1"},
    )
    assert r["resolved_mode"] in ("warn_gated", "autonomous")
    assert r["transition_blocked"] is False


def test_partial_adjudication_blocks_transition():
    history = [{"outcome": "accept"}] * 5
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-4",
        confidence=0.8,
        decision_history=history,
        prior_mode="shadow",
        adjudication_bundle={"cde_decision": "allow"},
    )
    assert r["transition_blocked"] is True


def test_calibration_gap_near_zero_for_matched_confidence():
    history = [{"outcome": "accept"}, {"outcome": "accept"}, {"outcome": "accept"}]
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-5",
        confidence=1.0,
        decision_history=history,
    )
    assert r["calibration_gap"] == 0.0


def test_mode_regression_allowed_without_adjudication():
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-6",
        confidence=0.5,
        decision_history=[{"outcome": "reject"}] * 4,
        prior_mode="warn_gated",
    )
    assert r["desired_mode"] == "shadow"
    assert r["resolved_mode"] == "warn_gated"


def test_stays_in_mode_when_desired_equals_prior():
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-7",
        confidence=0.5,
        decision_history=[],
        prior_mode="shadow",
    )
    assert r["resolved_mode"] == "shadow"
    assert r["transition_blocked"] is False


def test_autonomous_mode_executes():
    history = [{"outcome": "accept"}] * 10
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-8",
        confidence=0.95,
        decision_history=history,
        prior_mode="shadow",
        adjudication_bundle={"cde_decision": "allow", "tpa_record": "TPA-1"},
    )
    assert r["resolved_mode"] == "autonomous"
    assert r["execute"] is True


def test_thresholds_embedded():
    r = assess_trust(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-9", confidence=0.5
    )
    assert r["thresholds"]["shadow_to_warn_gated"] == SHADOW_TO_WARN_GATED
    assert r["thresholds"]["warn_gated_to_autonomous"] == WARN_GATED_TO_AUTO


def test_invalid_prior_mode_defaults_to_shadow():
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-10",
        confidence=0.5,
        prior_mode="made_up",
    )
    assert r["prior_mode"] == "shadow"


def test_schema_version_is_1_1_0():
    r = assess_trust(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-v", confidence=0.5
    )
    assert r["schema_version"] == "1.1.0"


def test_phase_attribution_default_empty():
    """Without phase_id/phase_name, the legacy shape works as before."""
    r = assess_trust(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-p1", confidence=0.5
    )
    assert r["phase_id"] == ""
    assert r["phase_name"] == ""
    validate_artifact(r, "rge_trust_record")


def test_phase_attribution_propagated():
    """When phase_id/phase_name are supplied, they appear on the record."""
    r = assess_trust(
        run_id=_RUN,
        trace_id=_TRACE,
        recommendation_id="rec-p2",
        confidence=0.7,
        phase_id="STR-EVL",
        phase_name="Strengthen EVL drift leg",
    )
    assert r["phase_id"] == "STR-EVL"
    assert r["phase_name"] == "Strengthen EVL drift leg"


def test_phase_attribution_changes_record_id():
    """Same recommendation, different phase -> different record_id."""
    base = dict(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-shared",
        confidence=0.7, prior_mode="shadow",
    )
    r1 = assess_trust(**base, phase_id="P1", phase_name="A")
    r2 = assess_trust(**base, phase_id="P2", phase_name="B")
    r_legacy = assess_trust(**base)
    assert r1["record_id"] != r2["record_id"]
    assert r1["record_id"] != r_legacy["record_id"]


def test_decision_counts_tally_outcomes():
    history = (
        [{"outcome": "accept"}] * 5
        + [{"outcome": "reject"}] * 2
        + [{"outcome": "override"}] * 1
        + [{"outcome": "unknown_thing"}] * 1
    )
    r = assess_trust(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-c1",
        confidence=0.6, decision_history=history,
    )
    counts = r["decision_counts"]
    assert counts["accepted"] == 5
    assert counts["rejected"] == 2
    assert counts["overridden"] == 1
    assert counts["unknown"] == 1
    assert counts["total"] == 9


def test_decision_counts_zero_when_no_history():
    r = assess_trust(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-c2", confidence=0.5
    )
    counts = r["decision_counts"]
    assert counts == {
        "accepted": 0, "rejected": 0, "overridden": 0, "unknown": 0, "total": 0,
    }


def test_phase_attribution_does_not_change_trust_logic():
    """Adding phase_id must not affect mode resolution or execute flag."""
    history = [{"outcome": "accept"}] * 10
    common = dict(
        run_id=_RUN, trace_id=_TRACE, recommendation_id="rec-eq",
        confidence=0.95, decision_history=history, prior_mode="shadow",
        adjudication_bundle={"cde_decision": "allow", "tpa_record": "TPA-1"},
    )
    r_no_phase = assess_trust(**common)
    r_with_phase = assess_trust(**common, phase_id="P1", phase_name="Alpha")
    assert r_no_phase["resolved_mode"] == r_with_phase["resolved_mode"]
    assert r_no_phase["execute"] == r_with_phase["execute"]
    assert r_no_phase["evidence_coverage_score"] == r_with_phase["evidence_coverage_score"]
