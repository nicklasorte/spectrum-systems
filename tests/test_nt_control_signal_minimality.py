"""NT-16..18: Control signal minimality audit + observation hijack red team.

Validates:
  - hard trust signals can drive freeze/block (allowed)
  - observations can warn but never freeze/block by themselves
  - unknown signals are flagged so they can't smuggle into a hard slot
  - every block/freeze must carry a canonical reason
  - every block/freeze must point to evidence_refs
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.control_signal_minimality import (
    CANONICAL_MINIMALITY_REASON_CODES,
    HARD_TRUST_SIGNAL_NAMES,
    OBSERVATION_ONLY_SIGNAL_NAMES,
    ControlSignalMinimalityError,
    audit_control_signal_minimality,
    classify_signal,
)


# ---- NT-16 contract ----


def test_hard_trust_signals_finite_and_known() -> None:
    expected_subset = {
        "required_eval_pass_status",
        "replay_match_status",
        "lineage_completeness_status",
        "context_admissibility_status",
        "authority_shape_preflight_status",
        "registry_validation_status",
        "certification_evidence_index_status",
        "trust_artifact_freshness_status",
    }
    assert expected_subset.issubset(set(HARD_TRUST_SIGNAL_NAMES))


def test_observation_signals_finite_and_known() -> None:
    for name in (
        "dashboard_freshness_seconds",
        "report_volume",
        "advisory_recommendation_count",
        "cosmetic_formatting_score",
    ):
        assert name in OBSERVATION_ONLY_SIGNAL_NAMES


def test_classify_signal_known_inputs() -> None:
    assert classify_signal("required_eval_pass_status") == "hard_trust"
    assert classify_signal("dashboard_freshness_seconds") == "observation"
    assert classify_signal("totally_unknown") == "unknown"


def test_canonical_reason_codes_finite() -> None:
    assert "MINIMALITY_OK" in CANONICAL_MINIMALITY_REASON_CODES
    assert "MINIMALITY_OBSERVATION_HIJACK" in CANONICAL_MINIMALITY_REASON_CODES
    assert "MINIMALITY_UNKNOWN_SIGNAL" in CANONICAL_MINIMALITY_REASON_CODES


# ---- NT-17 red team — observation hijack ----


def test_red_team_block_using_only_report_count_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "EVAL_FAILURE"},
        signals_used={"report_count": 5000},
        evidence_refs=["evl-1"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "MINIMALITY_OBSERVATION_HIJACK"


def test_red_team_freeze_using_dashboard_freshness_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "freeze", "canonical_reason": "CERTIFICATION_GAP"},
        signals_used={"dashboard_freshness_seconds": 999},
        evidence_refs=["cei-1"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "MINIMALITY_OBSERVATION_HIJACK"


def test_red_team_block_using_advisory_recommendation_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "POLICY_MISMATCH"},
        signals_used={"advisory_recommendation_count": 99},
        evidence_refs=["ref-1"],
    )
    assert res["decision"] == "block"


def test_red_team_block_using_cosmetic_formatting_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "POLICY_MISMATCH"},
        signals_used={"cosmetic_formatting_score": 0.99},
        evidence_refs=["x"],
    )
    assert res["decision"] == "block"


def test_red_team_block_with_unknown_signal_only_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "EVAL_FAILURE"},
        signals_used={"made_up_signal": "fail"},
        evidence_refs=["x"],
    )
    assert res["decision"] == "block"
    # First-failure-wins: observation hijack catches it before unknown.
    assert res["reason_code"] == "MINIMALITY_OBSERVATION_HIJACK"
    assert "made_up_signal" in res["unknown_signals"]


# ---- NT-17: real hard signal degradation passes minimality ----


def test_real_hard_signal_eval_failure_blocks_pass_minimality() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "EVAL_FAILURE"},
        signals_used={"required_eval_pass_status": "fail"},
        evidence_refs=["evl-bad"],
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "MINIMALITY_OK"
    assert "required_eval_pass_status" in res["hard_trust_used"]


def test_real_hard_signal_replay_mismatch_blocks_pass_minimality() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "freeze", "canonical_reason": "REPLAY_MISMATCH"},
        signals_used={"replay_match_status": "mismatch"},
        evidence_refs=["rpl-1"],
    )
    assert res["decision"] == "allow"


def test_real_hard_signal_freshness_stale_blocks_pass_minimality() -> None:
    """NT-16 promotes trust artifact freshness to a hard signal."""
    res = audit_control_signal_minimality(
        proposed_decision={
            "decision": "block",
            "canonical_reason": "CERTIFICATION_GAP",
        },
        signals_used={"trust_artifact_freshness_status": "stale"},
        evidence_refs=["aud-1"],
    )
    assert res["decision"] == "allow"


# ---- NT-18: missing canonical reason / evidence ----


def test_block_without_canonical_reason_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": ""},
        signals_used={"required_eval_pass_status": "fail"},
        evidence_refs=["evl-bad"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "MINIMALITY_MISSING_CANONICAL_REASON"


def test_block_without_evidence_refs_blocks() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "EVAL_FAILURE"},
        signals_used={"required_eval_pass_status": "fail"},
        evidence_refs=[],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "MINIMALITY_MISSING_EVIDENCE_REF"


# ---- NT-18: warn on observations is allowed ----


def test_warn_with_observation_only_passes() -> None:
    """Observations may produce a warn — that's exactly their role."""
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "warn", "canonical_reason": ""},
        signals_used={"dashboard_freshness_seconds": 9999},
    )
    # warn does not require canonical_reason or evidence_refs by NT-18 policy.
    assert res["decision"] == "allow"


def test_allow_with_no_signals_passes() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "allow"},
        signals_used={},
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "MINIMALITY_OK"
