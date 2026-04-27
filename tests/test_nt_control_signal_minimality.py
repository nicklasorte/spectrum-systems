"""NT-16..18: Control signal minimality — audit + red team + boundary fix.

Verifies that only hard trust signals can drive freeze/block. Observation
hijack attempts (using dashboard freshness, report counts, advisory
recommendations) must be rejected. Real hard-signal degradation continues
to drive freeze/block via the existing SLO signal diet.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.control_signal_minimality import (
    ControlSignalMinimalityError,
    HARD_TRUST_SIGNALS_NT,
    OBSERVATION_ONLY_SIGNALS,
    list_hard_trust_signals,
    list_observation_only_signals,
    validate_control_signal_minimality,
)
from spectrum_systems.modules.runtime.slo_budget_gate import (
    evaluate_slo_signal_diet,
)


def test_hard_signals_include_nt_all_01_extensions():
    hard = set(list_hard_trust_signals())
    # Existing NS-22 hard signals
    assert "required_eval_pass_status" in hard
    assert "replay_match_status" in hard
    # NT-ALL-01 extensions
    assert "artifact_tier_validity_status" in hard
    assert "trust_artifact_freshness_status" in hard


def test_observation_only_signals_are_listed():
    obs = set(list_observation_only_signals())
    for k in (
        "dashboard_freshness",
        "report_count",
        "advisory_recommendation",
        "non_critical_trend_note",
        "cosmetic_proof_formatting",
    ):
        assert k in obs


def test_only_hard_signals_admitted_when_clean():
    res = validate_control_signal_minimality(
        hard_signals_observed={
            "required_eval_pass_status": "pass",
            "replay_match_status": "match",
        },
        observation_signals={"dashboard_freshness": "stale"},
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "CONTROL_SIGNAL_MINIMALITY_OK"
    assert "required_eval_pass_status" in res["hard_signals_admitted"]
    assert "dashboard_freshness" in res["observations_admitted"]


def test_observation_hijack_via_dashboard_freshness_blocks():
    """Red team: caller proposes dashboard_freshness as a block driver."""
    res = validate_control_signal_minimality(
        hard_signals_observed={"required_eval_pass_status": "pass"},
        blocking_signal_keys=["dashboard_freshness"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_SIGNAL_OBSERVATION_USED_AS_HARD"
    assert any("dashboard_freshness" in r for r in res["blocking_reasons"])


def test_observation_hijack_via_report_count_blocks():
    res = validate_control_signal_minimality(
        hard_signals_observed={"required_eval_pass_status": "pass"},
        blocking_signal_keys=["report_count"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_SIGNAL_OBSERVATION_USED_AS_HARD"


def test_observation_hijack_via_advisory_recommendation_blocks():
    res = validate_control_signal_minimality(
        hard_signals_observed={"required_eval_pass_status": "pass"},
        blocking_signal_keys=["advisory_recommendation"],
    )
    assert res["decision"] == "block"


def test_cosmetic_proof_formatting_cannot_block():
    res = validate_control_signal_minimality(
        hard_signals_observed={"required_eval_pass_status": "pass"},
        blocking_signal_keys=["cosmetic_proof_formatting"],
    )
    assert res["decision"] == "block"
    assert any(
        "cosmetic_proof_formatting" in r for r in res["blocking_reasons"]
    )


def test_non_hard_signal_in_hard_slot_is_rejected():
    res = validate_control_signal_minimality(
        hard_signals_observed={
            "required_eval_pass_status": "pass",
            "ui_render_time": "200ms",  # not a hard trust signal
        },
    )
    assert res["decision"] == "block"
    assert "ui_render_time" in res["rejected_keys"]


def test_real_hard_signal_degradation_still_freezes():
    """The existing SLO signal diet must continue to freeze/block on real
    hard-signal degradation. NT-16/18 must not weaken that path."""
    res = evaluate_slo_signal_diet(
        signals={
            "required_eval_pass_status": "fail",
        }
    )
    assert res["decision"] == "block"
    assert res["canonical_category"] == "EVAL_FAILURE"


def test_real_replay_mismatch_still_blocks():
    res = evaluate_slo_signal_diet(
        signals={
            "replay_match_status": "mismatch",
        }
    )
    assert res["decision"] == "block"
    assert res["canonical_category"] == "REPLAY_MISMATCH"


def test_validate_requires_mapping():
    with pytest.raises(ControlSignalMinimalityError):
        validate_control_signal_minimality(hard_signals_observed="not a mapping")  # type: ignore[arg-type]


def test_combined_observation_hijack_and_real_signal():
    """Red team combo: real hard signal blocks via SLO diet, audit catches
    the hijack attempt independently."""
    audit = validate_control_signal_minimality(
        hard_signals_observed={"replay_match_status": "mismatch"},
        blocking_signal_keys=["dashboard_freshness", "report_count"],
    )
    assert audit["decision"] == "block"
    assert "dashboard_freshness" in str(audit["blocking_reasons"])
    assert "report_count" in str(audit["blocking_reasons"])


def test_no_signals_at_all_is_allow():
    """Empty hard-signal map with no observation hijack is OK; the SLO
    diet handles missing signals separately. NT-16 only audits the
    minimality boundary."""
    res = validate_control_signal_minimality(
        hard_signals_observed={},
    )
    assert res["decision"] == "allow"
