"""NS-22..24: SLO signal diet — hard trust signals only, observation-only
metrics never freeze/block."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.slo_budget_gate import (
    HARD_TRUST_SIGNALS,
    SIGNAL_DIET_REASON_CODES,
    SLOGateError,
    evaluate_slo_signal_diet,
)


def _all_passing_signals() -> dict:
    return {
        "required_eval_pass_status": "pass",
        "replay_match_status": "match",
        "lineage_completeness_status": "healthy",
        "context_admissibility_status": "allow",
        "authority_shape_preflight_status": "pass",
        "registry_validation_status": "pass",
        "certification_evidence_index_status": "ready",
    }


def test_diet_signals_finite_and_known() -> None:
    assert set(HARD_TRUST_SIGNALS) == {
        "required_eval_pass_status",
        "replay_match_status",
        "lineage_completeness_status",
        "context_admissibility_status",
        "authority_shape_preflight_status",
        "registry_validation_status",
        "certification_evidence_index_status",
    }


def test_all_passing_signals_allow() -> None:
    res = evaluate_slo_signal_diet(signals=_all_passing_signals())
    assert res["decision"] == "allow"
    assert res["reason_code"] == "SLO_DIET_OK"
    assert res["canonical_category"] is None


# ---- NS-23: degrade observation-only metrics → no freeze/block ----


def test_observation_only_drift_does_not_block() -> None:
    """Even if peripheral metrics like cpu/disk/dashboard_render_ms degrade,
    SLO signal diet must not freeze/block."""
    res = evaluate_slo_signal_diet(
        signals=_all_passing_signals(),
        observation_only={
            "cpu_utilization": 0.99,
            "disk_iops": 0.1,
            "dashboard_render_ms": 5000,
            "drift_rate": 0.99,
        },
    )
    assert res["decision"] == "allow"
    assert "drift_rate" in res["ignored_observations"]
    assert "dashboard_render_ms" in res["ignored_observations"]


def test_unknown_signal_in_hard_slot_rejected() -> None:
    """Caller must NOT smuggle observation metrics into the hard signal slot."""
    bad = _all_passing_signals()
    bad["dashboard_freshness_seconds"] = 999
    with pytest.raises(SLOGateError):
        evaluate_slo_signal_diet(signals=bad)


# ---- NS-23: degrade hard trust signals → freeze/block ----


def test_eval_failure_blocks() -> None:
    sig = _all_passing_signals()
    sig["required_eval_pass_status"] = "fail"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["reason_code"] == "SLO_DIET_EVAL_FAILURE"
    assert res["canonical_category"] == "EVAL_FAILURE"


def test_replay_mismatch_blocks() -> None:
    sig = _all_passing_signals()
    sig["replay_match_status"] = "mismatch"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["canonical_category"] == "REPLAY_MISMATCH"


def test_replay_indeterminate_blocks() -> None:
    sig = _all_passing_signals()
    sig["replay_match_status"] = "indeterminate"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"


def test_lineage_blocks() -> None:
    sig = _all_passing_signals()
    sig["lineage_completeness_status"] = "blocked"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["canonical_category"] == "LINEAGE_GAP"


def test_context_admission_blocks() -> None:
    sig = _all_passing_signals()
    sig["context_admissibility_status"] = "block"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["canonical_category"] == "CONTEXT_ADMISSION_FAILURE"


def test_authority_shape_failure_blocks() -> None:
    sig = _all_passing_signals()
    sig["authority_shape_preflight_status"] = "fail"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["canonical_category"] == "AUTHORITY_SHAPE_VIOLATION"


def test_registry_violation_blocks() -> None:
    sig = _all_passing_signals()
    sig["registry_validation_status"] = "fail"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["canonical_category"] == "POLICY_MISMATCH"


def test_certification_blocked_blocks() -> None:
    sig = _all_passing_signals()
    sig["certification_evidence_index_status"] = "blocked"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    assert res["canonical_category"] == "CERTIFICATION_GAP"


def test_certification_frozen_freezes() -> None:
    sig = _all_passing_signals()
    sig["certification_evidence_index_status"] = "frozen"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "freeze"
    assert res["canonical_category"] == "CERTIFICATION_GAP"


# ---- NS-23: reason categories remain clear ----


def test_reason_categories_are_canonical_when_blocking() -> None:
    sig = _all_passing_signals()
    sig["required_eval_pass_status"] = "fail"
    sig["replay_match_status"] = "mismatch"
    res = evaluate_slo_signal_diet(signals=sig)
    assert res["decision"] == "block"
    # First-failure-wins for canonical_category determinism
    assert res["canonical_category"] == "EVAL_FAILURE"
    assert any("eval" in r.lower() for r in res["blocking_reasons"])
    assert any("replay" in r.lower() for r in res["blocking_reasons"])


def test_reason_codes_set_finite() -> None:
    assert "SLO_DIET_OK" in SIGNAL_DIET_REASON_CODES
    assert "SLO_DIET_EVAL_FAILURE" in SIGNAL_DIET_REASON_CODES
    assert "SLO_DIET_CERTIFICATION_GAP" in SIGNAL_DIET_REASON_CODES
