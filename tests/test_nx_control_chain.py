"""NX-16..18: Control loop invariants + adversarial bypass fixtures."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.control_chain_invariants import (
    CANONICAL_CONTROL_REASON_CODES,
    ControlChainViolation,
    verify_control_chain,
)


def _eval_summary(trace_id="t1", artifact_id="evl-1") -> dict:
    return {
        "artifact_type": "eval_slice_summary",
        "artifact_id": artifact_id,
        "trace_id": trace_id,
        "status": "healthy",
    }


def _control_decision(eval_ref="evl-1", trace_id="t1", decision="allow") -> dict:
    return {
        "artifact_type": "control_decision",
        "decision_id": "cde-1",
        "decision": decision,
        "input_eval_summary_reference": eval_ref,
        "trace_id": trace_id,
    }


def _enforcement(decision_ref="cde-1", trace_id="t1", action="allow_execution") -> dict:
    return {
        "artifact_type": "enforcement_action",
        "enforcement_id": "sel-1",
        "enforcement_action": action,
        "input_decision_reference": decision_ref,
        "trace_id": trace_id,
    }


def test_full_chain_allows() -> None:
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=_control_decision(),
        enforcement_action=_enforcement(),
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "CONTROL_OK"


# ---- NX-17: red-team control bypass fixtures ----


def test_red_team_enforcement_without_decision_blocks() -> None:
    enforcement = _enforcement()
    enforcement["input_decision_reference"] = ""
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=_control_decision(),
        enforcement_action=enforcement,
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_ENFORCEMENT_WITHOUT_DECISION"


def test_red_team_decision_without_eval_summary_blocks() -> None:
    decision = _control_decision()
    decision["input_eval_summary_reference"] = ""
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=decision,
        enforcement_action=_enforcement(),
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_DECISION_WITHOUT_EVAL_SUMMARY"


def test_red_team_policy_bypass_blocks() -> None:
    """SEL allow_execution while CDE decided block must be detected."""
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=_control_decision(decision="block"),
        enforcement_action=_enforcement(action="allow_execution"),
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_POLICY_BYPASS"


def test_red_team_decision_enforcement_id_mismatch_blocks() -> None:
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=_control_decision(),
        enforcement_action=_enforcement(decision_ref="cde-different"),
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_DECISION_ENFORCEMENT_MISMATCH"


def test_red_team_trace_continuity_break_blocks() -> None:
    res = verify_control_chain(
        eval_summary=_eval_summary(trace_id="t1"),
        control_decision=_control_decision(trace_id="t2"),
        enforcement_action=_enforcement(trace_id="t1"),
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_TRACE_MISMATCH"


def test_red_team_promotion_without_certification_blocks() -> None:
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=_control_decision(),
        enforcement_action=_enforcement(),
        certification_record=None,
        require_certification=True,
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_PROMOTION_WITHOUT_CERTIFICATION"


def test_red_team_promotion_with_failed_certification_blocks() -> None:
    res = verify_control_chain(
        eval_summary=_eval_summary(),
        control_decision=_control_decision(),
        enforcement_action=_enforcement(),
        certification_record={
            "certification_id": "cert-1",
            "status": "fail",
            "trace_id": "t1",
        },
        require_certification=True,
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CONTROL_PROMOTION_WITHOUT_CERTIFICATION"


def test_red_team_invalid_inputs_raise() -> None:
    with pytest.raises(ControlChainViolation):
        verify_control_chain(
            eval_summary="not a dict",  # type: ignore[arg-type]
            control_decision=_control_decision(),
            enforcement_action=_enforcement(),
        )


def test_canonical_reason_codes_finite() -> None:
    assert "CONTROL_OK" in CANONICAL_CONTROL_REASON_CODES
    assert "CONTROL_POLICY_BYPASS" in CANONICAL_CONTROL_REASON_CODES
