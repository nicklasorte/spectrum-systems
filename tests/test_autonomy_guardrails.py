from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.autonomy_guardrails import evaluate_autonomy_guardrails


def _policy() -> dict:
    return copy.deepcopy(load_example("autonomy_policy"))


def test_continue_when_all_guardrail_conditions_satisfied() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    validate_artifact(record, "autonomy_decision_record")
    assert record["decision"] == "continue"
    assert record["reason_codes"] == ["all_continue_conditions_satisfied"]


def test_stop_on_unresolved_critical_risk_threshold() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=["critical_risk:AUTH_REVIEW_PENDING"],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    assert record["decision"] == "stop"
    assert "critical_risk_threshold_exceeded" in record["reason_codes"]


def test_require_human_review_on_configured_review_condition() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="required",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    assert record["decision"] == "require_human_review"
    assert "review_gate_required" in record["reason_codes"]


def test_escalate_on_configured_escalation_condition() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "freeze"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="passed",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    assert record["decision"] == "escalate"
    assert "control_decision_freeze" in record["reason_codes"]


def test_stop_on_replay_failure_when_policy_requires() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="failed",
        review_gate_status="passed",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    assert record["decision"] == "stop"
    assert "replay_failure_stop" in record["reason_codes"]


def test_fail_closed_on_missing_or_malformed_policy() -> None:
    missing = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=None,
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="passed",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    malformed_policy = _policy()
    malformed_policy.pop("continue_conditions", None)
    malformed = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=malformed_policy,
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="passed",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    assert missing["decision"] == "stop"
    assert malformed["decision"] == "stop"
    assert "malformed_autonomy_policy" in missing["reason_codes"]
    assert "malformed_autonomy_policy" in malformed["reason_codes"]


def test_deterministic_autonomy_decision_for_same_inputs() -> None:
    kwargs = dict(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    first = evaluate_autonomy_guardrails(**kwargs)
    second = evaluate_autonomy_guardrails(**kwargs)
    assert first == second
