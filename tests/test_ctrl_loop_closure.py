"""Comprehensive CTRL-LOOP gate closure tests — all 8 checks.

Tests verify that each gate check correctly identifies PASS and BLOCKED
conditions, and that run_all_gate_checks produces the right overall status.
"""
from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.ctrl_loop_gates import (
    check_calibration_affects_lifecycle,
    check_deterministic_policy_consumption,
    check_failure_eval_policy_linkage,
    check_falsification_artifact,
    check_longitudinal_calibration,
    check_policy_causes_behavior_change,
    check_recurrence_prevention_wired,
    check_replay_trace_reconstruct,
    run_all_gate_checks,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _failure(failure_id: str = "F-001") -> dict:
    return {
        "failure_id": failure_id,
        "failure_class": "runtime_failure",
        "artifact_type": "failure_record",
    }


def _eval_candidate(failure_id: str = "F-001") -> dict:
    return {
        "eval_case_id": f"EC-{failure_id}",
        "source_failure_id": failure_id,
        "artifact_type": "failure_eval_case",
    }


def _decision(
    system_response: str = "allow",
    decision_id: str = "ECD-001",
    policy_artifact_id: str = "POL-001",
) -> dict:
    return {
        "artifact_type": "evaluation_control_decision",
        "decision_id": decision_id,
        "system_response": system_response,
        "decision": "allow" if system_response == "allow" else "deny",
        "policy_artifact_id": policy_artifact_id,
    }


def _calibration_record(
    disagreement_rate: float = 0.10,
    window: str = "7d",
) -> dict:
    return {
        "artifact_type": "judge_calibration_record",
        "window": window,
        "disagreement_rate": disagreement_rate,
        "sample_count": 100,
        "calibration_status": "calibrated" if disagreement_rate < 0.25 else "out_of_calibration",
    }


def _promotion_decision(
    can_auto_promote: bool = True,
    requires_human_review: bool = False,
) -> dict:
    return {
        "artifact_type": "lifecycle_promotion_decision",
        "can_auto_promote": can_auto_promote,
        "requires_human_review": requires_human_review,
    }


# ---------------------------------------------------------------------------
# Check 1: Failure → eval → policy linkage
# ---------------------------------------------------------------------------

class TestCheck1FailureEvalPolicyLinkage:
    def test_pass_all_present(self) -> None:
        result = check_failure_eval_policy_linkage(
            _failure(),
            _eval_candidate(),
            "policy:POL-001",
        )
        assert result["status"] == "PASS"

    def test_blocked_no_eval_candidate(self) -> None:
        result = check_failure_eval_policy_linkage(_failure(), None, "policy:POL-001")
        assert result["status"] == "BLOCKED"
        assert "eval_candidate" in str(result["evidence"]["issues"])

    def test_blocked_no_policy_ref(self) -> None:
        result = check_failure_eval_policy_linkage(_failure(), _eval_candidate(), None)
        assert result["status"] == "BLOCKED"

    def test_blocked_eval_candidate_not_linked_to_failure(self) -> None:
        bad_candidate = {"eval_case_id": "EC-999"}
        result = check_failure_eval_policy_linkage(_failure("F-001"), bad_candidate, "policy:POL-001")
        assert result["status"] == "BLOCKED"

    def test_blocked_non_dict_failure(self) -> None:
        result = check_failure_eval_policy_linkage("not_a_dict", _eval_candidate(), "policy:POL-001")
        assert result["status"] == "BLOCKED"

    def test_gate_result_has_correct_type(self) -> None:
        result = check_failure_eval_policy_linkage(_failure(), _eval_candidate(), "policy:P")
        assert result["artifact_type"] == "ctrl_loop_gate_result"
        assert result["gate_check_id"] == "CTRL-1-failure-eval-policy-linkage"


# ---------------------------------------------------------------------------
# Check 2: Deterministic policy consumption
# ---------------------------------------------------------------------------

class TestCheck2DeterministicPolicyConsumption:
    def test_pass_all_decisions_same_policy(self) -> None:
        decisions = [_decision(policy_artifact_id="POL-001") for _ in range(5)]
        result = check_deterministic_policy_consumption(decisions, expected_policy_artifact_id="POL-001")
        assert result["status"] == "PASS"

    def test_blocked_no_policy_ref_in_decisions(self) -> None:
        decisions = [{"decision": "allow"} for _ in range(3)]
        result = check_deterministic_policy_consumption(decisions)
        assert result["status"] == "BLOCKED"

    def test_blocked_multiple_policy_refs(self) -> None:
        decisions = [
            _decision(policy_artifact_id="POL-001"),
            _decision(policy_artifact_id="POL-002"),
        ]
        result = check_deterministic_policy_consumption(decisions)
        assert result["status"] == "BLOCKED"
        assert "Non-deterministic policy" in str(result["notes"])

    def test_blocked_inline_policy_text(self) -> None:
        decisions = [{"decision": "allow", "policy_artifact_id": "POL-001", "policy_text": "allow all"}]
        result = check_deterministic_policy_consumption(decisions)
        assert result["status"] == "BLOCKED"

    def test_blocked_non_deterministic_outcomes(self) -> None:
        decisions = [
            {**_decision("allow"), "policy_artifact_id": "POL-001"},
            {**_decision("block"), "policy_artifact_id": "POL-001"},
        ]
        result = check_deterministic_policy_consumption(decisions)
        assert result["status"] == "BLOCKED"

    def test_blocked_empty_decisions(self) -> None:
        result = check_deterministic_policy_consumption([])
        assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Check 3: Policy causes behavior change
# ---------------------------------------------------------------------------

class TestCheck3PolicyCausesBehaviorChange:
    def test_pass_30_percent_different(self) -> None:
        a = ["allow"] * 7 + ["block"] * 3
        b = ["allow"] * 3 + ["block"] * 7
        result = check_policy_causes_behavior_change(a, b)
        assert result["status"] == "PASS"

    def test_blocked_identical_outcomes(self) -> None:
        a = ["allow"] * 10
        b = ["allow"] * 10
        result = check_policy_causes_behavior_change(a, b)
        assert result["status"] == "BLOCKED"

    def test_blocked_change_rate_below_threshold(self) -> None:
        a = ["allow"] * 10
        b = ["allow"] * 8 + ["block"] * 2
        result = check_policy_causes_behavior_change(a, b)
        assert result["status"] == "BLOCKED"

    def test_pass_100_percent_different(self) -> None:
        a = ["allow"] * 5
        b = ["block"] * 5
        result = check_policy_causes_behavior_change(a, b)
        assert result["status"] == "PASS"

    def test_blocked_empty_lists(self) -> None:
        result = check_policy_causes_behavior_change([], [])
        assert result["status"] == "BLOCKED"

    def test_custom_min_change_rate(self) -> None:
        a = ["allow"] * 9 + ["block"]
        b = ["allow"] * 8 + ["block"] * 2
        result = check_policy_causes_behavior_change(a, b, min_change_rate=0.05)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Check 4: Recurrence prevention
# ---------------------------------------------------------------------------

class TestCheck4RecurrencePrevention:
    def test_pass_second_occurrence_freezes(self) -> None:
        first = _decision("block")
        second = {**_decision("freeze"), "recurrence_count": 2}
        result = check_recurrence_prevention_wired(first, second, failure_id="F-001")
        assert result["status"] == "PASS"

    def test_blocked_second_occurrence_allows(self) -> None:
        first = _decision("block")
        second = _decision("allow")
        result = check_recurrence_prevention_wired(first, second, failure_id="F-001")
        assert result["status"] == "BLOCKED"

    def test_blocked_second_occurrence_warns_not_freezes(self) -> None:
        first = _decision("warn")
        second = _decision("warn")
        result = check_recurrence_prevention_wired(first, second, failure_id="F-002")
        assert result["status"] == "BLOCKED"

    def test_blocked_first_occurrence_allows(self) -> None:
        first = _decision("allow")
        second = _decision("freeze")
        result = check_recurrence_prevention_wired(first, second, failure_id="F-003")
        assert result["status"] == "BLOCKED"

    def test_pass_first_warn_second_freeze(self) -> None:
        first = _decision("warn")
        second = {**_decision("freeze"), "recurrence_count": 2}
        result = check_recurrence_prevention_wired(first, second, failure_id="F-004")
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Check 5: Longitudinal calibration
# ---------------------------------------------------------------------------

class TestCheck5LongitudinalCalibration:
    def test_pass_good_calibration_7d(self) -> None:
        result = check_longitudinal_calibration(_calibration_record(0.10, "7d"))
        assert result["status"] == "PASS"

    def test_blocked_wrong_window(self) -> None:
        result = check_longitudinal_calibration(_calibration_record(0.10, "30d"))
        assert result["status"] == "BLOCKED"

    def test_blocked_missing_rate(self) -> None:
        record = {"window": "7d", "sample_count": 100, "calibration_status": "calibrated"}
        result = check_longitudinal_calibration(record)
        assert result["status"] == "BLOCKED"

    def test_blocked_high_disagreement(self) -> None:
        result = check_longitudinal_calibration(_calibration_record(0.40, "7d"))
        assert result["status"] == "BLOCKED"

    def test_blocked_non_dict(self) -> None:
        result = check_longitudinal_calibration("not_a_dict")
        assert result["status"] == "BLOCKED"

    def test_pass_exactly_at_threshold(self) -> None:
        result = check_longitudinal_calibration(_calibration_record(0.25, "7d"))
        assert result["status"] == "BLOCKED"

    def test_pass_just_below_threshold(self) -> None:
        result = check_longitudinal_calibration(
            _calibration_record(0.249, "7d"),
            max_disagreement_threshold=0.25,
        )
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Check 6: Calibration affects lifecycle
# ---------------------------------------------------------------------------

class TestCheck6CalibrationAffectsLifecycle:
    def test_pass_high_disagreement_blocks_auto_promote(self) -> None:
        promotion = _promotion_decision(can_auto_promote=False, requires_human_review=True)
        calibration = _calibration_record(disagreement_rate=0.40)
        result = check_calibration_affects_lifecycle(promotion, calibration)
        assert result["status"] == "PASS"

    def test_blocked_high_disagreement_allows_auto_promote(self) -> None:
        promotion = _promotion_decision(can_auto_promote=True, requires_human_review=False)
        calibration = _calibration_record(disagreement_rate=0.40)
        result = check_calibration_affects_lifecycle(promotion, calibration)
        assert result["status"] == "BLOCKED"

    def test_pass_low_disagreement_can_auto_promote(self) -> None:
        promotion = _promotion_decision(can_auto_promote=True, requires_human_review=False)
        calibration = _calibration_record(disagreement_rate=0.10)
        result = check_calibration_affects_lifecycle(promotion, calibration)
        assert result["status"] == "PASS"

    def test_blocked_high_disagreement_missing_human_review_flag(self) -> None:
        promotion = {"can_auto_promote": False}
        calibration = _calibration_record(disagreement_rate=0.40)
        result = check_calibration_affects_lifecycle(promotion, calibration)
        assert result["status"] == "BLOCKED"

    def test_pass_custom_threshold(self) -> None:
        promotion = _promotion_decision(can_auto_promote=False, requires_human_review=True)
        calibration = _calibration_record(disagreement_rate=0.30)
        result = check_calibration_affects_lifecycle(
            promotion, calibration, high_disagreement_threshold=0.25
        )
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Check 7: Replay + trace reconstruct
# ---------------------------------------------------------------------------

class TestCheck7ReplayTraceReconstruct:
    def test_pass_identical_decisions(self) -> None:
        dec = _decision("block")
        result = check_replay_trace_reconstruct(dec, dec.copy())
        assert result["status"] == "PASS"

    def test_blocked_system_response_mismatch(self) -> None:
        original = _decision("block")
        replayed = {**original, "system_response": "allow"}
        result = check_replay_trace_reconstruct(original, replayed)
        assert result["status"] == "BLOCKED"

    def test_blocked_decision_field_mismatch(self) -> None:
        original = _decision("block")
        replayed = {**original, "decision": "allow"}
        result = check_replay_trace_reconstruct(original, replayed)
        assert result["status"] == "BLOCKED"

    def test_pass_irrelevant_field_differs(self) -> None:
        original = {**_decision("allow"), "extra_metadata": "foo"}
        replayed = {**_decision("allow"), "extra_metadata": "bar"}
        result = check_replay_trace_reconstruct(
            original, replayed, key_fields=["system_response", "decision"]
        )
        assert result["status"] == "PASS"

    def test_blocked_non_dict_input(self) -> None:
        result = check_replay_trace_reconstruct("not_a_dict", _decision())
        assert result["status"] == "BLOCKED"

    def test_evidence_shows_mismatched_fields(self) -> None:
        original = _decision("block")
        replayed = {**original, "system_response": "allow", "rationale_code": "wrong"}
        result = check_replay_trace_reconstruct(original, replayed)
        assert len(result["evidence"]["mismatched_fields"]) >= 1


# ---------------------------------------------------------------------------
# Check 8: Falsification artifact
# ---------------------------------------------------------------------------

class TestCheck8FalsificationArtifact:
    def test_pass_no_falsifying_policy_emits_finding(self) -> None:
        result = check_falsification_artifact(_decision("allow"), None)
        assert result["status"] == "PASS"
        assert result["evidence"]["falsifying_policy_exists"] is False
        assert "finding" in result["evidence"]

    def test_pass_falsifying_policy_changes_decision(self) -> None:
        original = _decision("allow")
        falsifying = {"artifact_type": "policy", "policy_id": "strict-001", "default_action": "block"}
        falsified_outcome = _decision("block")
        result = check_falsification_artifact(original, falsifying, falsified_outcome)
        assert result["status"] == "PASS"

    def test_blocked_falsifying_policy_same_outcome(self) -> None:
        original = _decision("allow")
        falsifying = {"artifact_type": "policy", "policy_id": "strict-001"}
        same_outcome = _decision("allow")
        result = check_falsification_artifact(original, falsifying, same_outcome)
        assert result["status"] == "BLOCKED"

    def test_blocked_falsifying_policy_no_outcome_provided(self) -> None:
        original = _decision("allow")
        falsifying = {"artifact_type": "policy", "policy_id": "strict-001"}
        result = check_falsification_artifact(original, falsifying, None)
        assert result["status"] == "BLOCKED"

    def test_finding_artifact_has_correct_structure(self) -> None:
        result = check_falsification_artifact(_decision("block"), None)
        finding = result["evidence"]["finding"]
        assert finding["artifact_type"] == "finding_artifact"
        assert finding["category"] == "no_falsifying_policy_found"

    def test_gate_result_schema_version(self) -> None:
        result = check_falsification_artifact(_decision("allow"), None)
        assert result["schema_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# run_all_gate_checks integration
# ---------------------------------------------------------------------------

class TestRunAllGateChecks:
    def _all_pass_inputs(self) -> dict:
        return {
            "failure": _failure("F-ALL-001"),
            "eval_candidate": _eval_candidate("F-ALL-001"),
            "policy_ref": "policy:POL-ALL-001",
            "repeated_decisions": [_decision("block") for _ in range(5)],
            "expected_policy_artifact_id": "POL-001",
            "outcomes_policy_a": ["allow"] * 3 + ["block"] * 7,
            "outcomes_policy_b": ["block"] * 3 + ["allow"] * 7,
            "first_recurrence_decision": _decision("block"),
            "second_recurrence_decision": {**_decision("freeze"), "recurrence_count": 2},
            "recurrence_failure_id": "F-REC-001",
            "calibration_record": _calibration_record(0.10, "7d"),
            "promotion_decision": _promotion_decision(True, False),
            "original_decision": _decision("block"),
            "replayed_decision": _decision("block"),
            "falsification_decision": _decision("allow"),
            "falsifying_policy": None,
        }

    def test_all_checks_pass_on_valid_inputs(self) -> None:
        result = run_all_gate_checks(self._all_pass_inputs())
        assert result["overall_status"] == "PASS", (
            f"Expected all 8 checks to pass; blocked: {result['blocked_check_ids']}"
        )
        assert result["checks_passed"] == 8
        assert result["checks_blocked"] == 0

    def test_blocked_when_one_check_fails(self) -> None:
        inputs = self._all_pass_inputs()
        inputs["eval_candidate"] = None  # Break check 1
        result = run_all_gate_checks(inputs)
        assert result["overall_status"] == "BLOCKED"
        assert "check_1" in result["blocked_check_ids"]

    def test_summary_has_correct_type(self) -> None:
        result = run_all_gate_checks(self._all_pass_inputs())
        assert result["artifact_type"] == "ctrl_loop_gate_summary"

    def test_summary_has_all_8_check_results(self) -> None:
        result = run_all_gate_checks(self._all_pass_inputs())
        for i in range(1, 9):
            assert f"check_{i}" in result["check_results"]

    def test_blocked_when_recurrence_not_wired(self) -> None:
        inputs = self._all_pass_inputs()
        inputs["second_recurrence_decision"] = _decision("warn")  # Should be freeze
        result = run_all_gate_checks(inputs)
        assert result["overall_status"] == "BLOCKED"
        assert "check_4" in result["blocked_check_ids"]

    def test_blocked_when_calibration_wrong_window(self) -> None:
        inputs = self._all_pass_inputs()
        inputs["calibration_record"] = _calibration_record(0.10, "30d")
        result = run_all_gate_checks(inputs)
        assert result["overall_status"] == "BLOCKED"
        assert "check_5" in result["blocked_check_ids"]

    def test_blocked_when_replay_diverges(self) -> None:
        inputs = self._all_pass_inputs()
        inputs["replayed_decision"] = _decision("allow")  # Different from original "block"
        result = run_all_gate_checks(inputs)
        assert result["overall_status"] == "BLOCKED"
        assert "check_7" in result["blocked_check_ids"]
