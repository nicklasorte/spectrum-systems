from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.autonomy_guardrails import (
    build_autonomy_audit_record,
    build_tpa_maturity_signal,
    evaluate_autonomy_guardrails,
    is_autonomy_allowed,
    summarize_autonomy_observability,
)


def _policy() -> dict:
    return copy.deepcopy(load_example("autonomy_policy"))


def _stable_maturity() -> dict:
    return build_tpa_maturity_signal(
        module="spectrum_systems/modules/runtime/system_cycle_operator.py",
        trend_stability=0.9,
        regression_frequency=0.05,
        test_coverage=0.9,
        drift_signal_strength=0.1,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )


def test_continue_when_all_guardrail_conditions_satisfied() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low", "volatility": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        system_budget_status={"cost_budget_status": "within_budget"},
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        tpa_maturity_signal=_stable_maturity(),
        system_health_mode="normal",
        target_module="spectrum_systems/modules/runtime/system_cycle_operator.py",
        requested_action="cleanup",
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
        drift_signals={"drift_level": "low", "volatility": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        system_budget_status={"cost_budget_status": "within_budget"},
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        tpa_maturity_signal=_stable_maturity(),
        system_health_mode="normal",
    )
    assert record["decision"] == "stop"
    assert "critical_risk_threshold_exceeded" in record["reason_codes"]


def test_require_human_review_on_configured_review_condition() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low", "volatility": "low"},
        replay_status="passed",
        review_gate_status="required",
        required_validation_carry_forward=[],
        system_budget_status={"cost_budget_status": "within_budget"},
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        tpa_maturity_signal=_stable_maturity(),
        system_health_mode="normal",
    )
    assert record["decision"] == "require_human_review"
    assert "review_gate_required" in record["reason_codes"]


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
        system_budget_status=None,
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        target_module="spectrum_systems/modules/runtime/system_cycle_operator.py",
        requested_action="cleanup",
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
        system_budget_status=None,
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        target_module="spectrum_systems/modules/runtime/system_cycle_operator.py",
        requested_action="cleanup",
    )
    assert missing["decision"] == "stop"
    assert malformed["decision"] == "stop"
    assert "malformed_autonomy_policy" in missing["reason_codes"]
    assert "malformed_autonomy_policy" in malformed["reason_codes"]


def test_scope_gate_and_fail_closed_on_missing_maturity_signal() -> None:
    allowed = is_autonomy_allowed(
        {
            "module": "spectrum_systems/modules/runtime/system_cycle_operator.py",
            "action": "cleanup",
            "trend": {"drift_level": "low", "volatility": "low"},
            "budget": {"cost_budget_status": "within_budget"},
        },
        autonomy_policy=_policy(),
    )
    blocked = is_autonomy_allowed(
        {
            "module": "spectrum_systems/modules/runtime/system_cycle_operator.py",
            "action": "policy_change",
            "trend": {"drift_level": "low", "volatility": "low"},
            "budget": {"cost_budget_status": "within_budget"},
        },
        autonomy_policy=_policy(),
    )
    assert allowed is True
    assert blocked is False

    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low", "volatility": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        system_budget_status={"cost_budget_status": "within_budget"},
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        target_module="spectrum_systems/modules/runtime/system_cycle_operator.py",
        requested_action="cleanup",
    )
    assert record["decision"] == "stop"
    assert "missing_required_signal:maturity" in record["reason_codes"]


def test_override_and_audit_trail_metrics() -> None:
    record = evaluate_autonomy_guardrails(
        source_cycle_id="RMB-EXAMPLE0001",
        autonomy_policy=_policy(),
        control_decisions=[{"decision": "allow"}],
        unresolved_critical_risks=[],
        drift_signals={"drift_level": "low", "volatility": "low"},
        replay_status="passed",
        review_gate_status="PASS",
        required_validation_carry_forward=[],
        system_budget_status={"cost_budget_status": "within_budget"},
        continuation_depth=0,
        consecutive_warn_count=0,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
        tpa_maturity_signal=_stable_maturity(),
        system_health_mode="normal",
        override_active=True,
        override_ref="override_governance_record:OVG-AAAAAAAAAAAA",
    )
    assert record["decision"] == "require_human_review"
    assert "human_override_active" in record["reason_codes"]

    success = build_autonomy_audit_record(
        action_type="cleanup",
        trigger_signal="stable trend",
        decision_context={"module": "m", "action": "cleanup"},
        outcome="success",
        timestamp="2026-04-04T00:00:00Z",
        trace_id="trace-a1-test",
    )
    blocked = build_autonomy_audit_record(
        action_type="cleanup",
        trigger_signal="missing required signal",
        decision_context={"module": "m", "action": "cleanup"},
        outcome="blocked",
        timestamp="2026-04-04T00:01:00Z",
        trace_id="trace-a1-test",
    )
    summary = summarize_autonomy_observability([success, blocked])
    assert summary["autonomy_action_count"] == 2.0
    assert summary["autonomy_success_rate"] == 0.5
