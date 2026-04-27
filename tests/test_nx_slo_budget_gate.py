"""NX-22..23: SLO/error-budget gate + adversarial drift fixtures."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.slo_budget_gate import (
    CANONICAL_SLO_REASON_CODES,
    SLOGateError,
    evaluate_slo_budget_gate,
)


def _healthy() -> dict:
    return {
        "trace_id": "t1",
        "budget_remaining": 0.9,
        "drift_rate": 0.0,
        "override_rate": 0.0,
        "eval_pass_rate": 0.99,
        "replay_mismatch_rate": 0.0,
    }


def test_healthy_posture_allows() -> None:
    res = evaluate_slo_budget_gate(posture=_healthy())
    assert res["decision"] == "allow"
    assert res["reason_code"] == "SLO_OK"


# ---- NX-23 red team ----


def test_red_team_exhausted_budget_blocks() -> None:
    posture = _healthy()
    posture["budget_remaining"] = 0.0
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "block"
    assert res["reason_code"] == "SLO_BUDGET_EXHAUSTED"


def test_red_team_low_budget_freezes() -> None:
    posture = _healthy()
    posture["budget_remaining"] = 0.03
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "freeze"
    assert res["reason_code"] == "SLO_BUDGET_EXHAUSTED"


def test_red_team_rising_drift_warns() -> None:
    posture = _healthy()
    posture["drift_rate"] = 0.15
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "warn"
    assert res["reason_code"] == "SLO_DRIFT_RISING"


def test_red_team_high_drift_freezes() -> None:
    posture = _healthy()
    posture["drift_rate"] = 0.4
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "freeze"


def test_red_team_repeated_override_rate_warns() -> None:
    posture = _healthy()
    posture["override_rate"] = 0.12
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "warn"
    assert res["reason_code"] == "SLO_OVERRIDE_RATE_EXCEEDED"


def test_red_team_repeated_override_rate_freezes() -> None:
    posture = _healthy()
    posture["override_rate"] = 0.5
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "freeze"


def test_red_team_eval_pass_rate_degraded_warns() -> None:
    posture = _healthy()
    posture["eval_pass_rate"] = 0.92
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "warn"
    assert res["reason_code"] == "SLO_EVAL_PASS_RATE_DEGRADED"


def test_red_team_eval_pass_rate_degraded_freezes() -> None:
    posture = _healthy()
    posture["eval_pass_rate"] = 0.5
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "freeze"


def test_red_team_replay_mismatch_rate_warns() -> None:
    posture = _healthy()
    posture["replay_mismatch_rate"] = 0.07
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "warn"
    assert res["reason_code"] == "SLO_REPLAY_MISMATCH_RATE_HIGH"


def test_red_team_replay_mismatch_rate_freezes() -> None:
    posture = _healthy()
    posture["replay_mismatch_rate"] = 0.5
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "freeze"


def test_red_team_invalid_posture_blocks() -> None:
    res = evaluate_slo_budget_gate(posture={"trace_id": "x"})  # missing budget_remaining
    assert res["decision"] == "block"
    assert res["reason_code"] == "SLO_INVALID_POSTURE"


def test_red_team_out_of_range_budget_blocks() -> None:
    res = evaluate_slo_budget_gate(posture={"trace_id": "x", "budget_remaining": 1.5})
    assert res["decision"] == "block"
    assert res["reason_code"] == "SLO_INVALID_POSTURE"


def test_invalid_inputs_raise() -> None:
    with pytest.raises(SLOGateError):
        evaluate_slo_budget_gate(posture="not a mapping")  # type: ignore[arg-type]


def test_canonical_reason_codes_finite() -> None:
    assert "SLO_OK" in CANONICAL_SLO_REASON_CODES
    assert "SLO_BUDGET_EXHAUSTED" in CANONICAL_SLO_REASON_CODES


def test_decision_escalation_picks_strongest() -> None:
    """Multiple signals → the most severe must win."""
    posture = _healthy()
    posture["drift_rate"] = 0.4  # freeze
    posture["override_rate"] = 0.12  # warn
    res = evaluate_slo_budget_gate(posture=posture)
    assert res["decision"] == "freeze"
    # the reason_code reflects the highest-severity signal
    assert res["reason_code"] in {"SLO_DRIFT_RISING", "SLO_OVERRIDE_RATE_EXCEEDED"}
