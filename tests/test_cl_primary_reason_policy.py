"""CL-22 / CL-23 / CL-24: primary reason policy, reason flood red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_primary_reason import (
    PrimaryReasonPolicyError,
    load_primary_reason_policy,
    next_action_for_class,
    select_primary_reason,
)


# --- CL-22 policy contract ---------------------------------------------


def test_cl22_policy_loads_with_canonical_precedence() -> None:
    p = load_primary_reason_policy()
    assert p["precedence_order"] == [
        "admission",
        "execution",
        "eval",
        "policy",
        "decision",
        "action",
    ]
    assert p["pass_reason_code"] == "CORE_LOOP_PASS"


def test_cl22_no_findings_returns_pass() -> None:
    primary = select_primary_reason(candidate_findings=[])
    assert primary["primary_canonical_reason"] == "CORE_LOOP_PASS"
    assert primary["source_stage"] == "NONE"
    assert primary["next_allowed_action"] == "allow_continuation"


def test_cl22_known_reason_classifies_into_admission_class() -> None:
    findings = [{"reason_code": "ADMISSION_CLASS_MISSING", "stage": "AEX"}]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "ADMISSION_CLASS_MISSING"
    assert primary["source_stage"] == "AEX"


# --- CL-23 reason flood -------------------------------------------------


def test_cl23_admission_beats_execution() -> None:
    findings = [
        {"reason_code": "EXECUTION_TRACE_ID_MISSING", "stage": "PQX"},
        {"reason_code": "ADMISSION_CLASS_MISSING", "stage": "AEX"},
    ]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "ADMISSION_CLASS_MISSING"
    assert primary["source_stage"] == "AEX"


def test_cl23_execution_beats_eval() -> None:
    findings = [
        {"reason_code": "EVAL_REQUIRED_MISSING", "stage": "EVL"},
        {"reason_code": "EXECUTION_RUN_ID_MISSING", "stage": "PQX"},
    ]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "EXECUTION_RUN_ID_MISSING"
    assert primary["source_stage"] == "PQX"


def test_cl23_eval_beats_policy() -> None:
    findings = [
        {"reason_code": "POLICY_HIDDEN_INPUT", "stage": "TPA"},
        {"reason_code": "EVAL_REQUIRED_FAILED", "stage": "EVL"},
    ]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "EVAL_REQUIRED_FAILED"


def test_cl23_policy_beats_decision() -> None:
    findings = [
        {"reason_code": "DECISION_INPUT_FREE_TEXT_ONLY", "stage": "CDE"},
        {"reason_code": "POLICY_DASHBOARD_ONLY_INPUT", "stage": "TPA"},
    ]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "POLICY_DASHBOARD_ONLY_INPUT"


def test_cl23_decision_beats_action() -> None:
    findings = [
        {"reason_code": "ACTION_PROMOTE_ON_BLOCK", "stage": "SEL"},
        {"reason_code": "DECISION_FREEZE_REQUIRED", "stage": "CDE"},
    ]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "DECISION_FREEZE_REQUIRED"


def test_cl23_supporting_reasons_preserved_after_election() -> None:
    findings = [
        {"reason_code": "ADMISSION_CLASS_MISSING", "stage": "AEX"},
        {"reason_code": "EXECUTION_TRACE_ID_MISSING", "stage": "PQX"},
        {"reason_code": "EVAL_REQUIRED_MISSING", "stage": "EVL"},
        {"reason_code": "POLICY_HIDDEN_INPUT", "stage": "TPA"},
        {"reason_code": "DECISION_INPUT_FREE_TEXT_ONLY", "stage": "CDE"},
        {"reason_code": "ACTION_PROMOTE_ON_BLOCK", "stage": "SEL"},
    ]
    primary = select_primary_reason(candidate_findings=findings)
    assert primary["primary_canonical_reason"] == "ADMISSION_CLASS_MISSING"
    supporting_codes = {s["reason_code"] for s in primary["supporting_reasons"]}
    assert "EXECUTION_TRACE_ID_MISSING" in supporting_codes
    assert "EVAL_REQUIRED_MISSING" in supporting_codes
    assert "POLICY_HIDDEN_INPUT" in supporting_codes
    assert "DECISION_INPUT_FREE_TEXT_ONLY" in supporting_codes
    assert "ACTION_PROMOTE_ON_BLOCK" in supporting_codes


# --- CL-24 fix pass: shape -----------------------------------------------


def test_cl24_primary_reason_shape() -> None:
    findings = [{"reason_code": "EXECUTION_OUTPUT_HASH_MISSING", "stage": "PQX",
                 "failing_artifact_refs": ["env-1"]}]
    primary = select_primary_reason(candidate_findings=findings)
    assert set(primary.keys()) == {
        "primary_canonical_reason",
        "source_stage",
        "supporting_reasons",
        "failing_artifact_refs",
        "next_allowed_action",
    }
    assert primary["failing_artifact_refs"] == ["env-1"]


def test_cl24_next_action_for_class_mapping() -> None:
    assert next_action_for_class("admission") == "block_no_mutation"
    assert next_action_for_class("decision") == "freeze_hold"
    assert next_action_for_class("action") == "block_no_mutation"
    assert next_action_for_class(None) == "no_action"
