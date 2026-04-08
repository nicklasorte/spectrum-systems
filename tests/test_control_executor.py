"""Tests for BN.6 Control Signal Consumption Layer."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_executor import (  # noqa: E402
    build_execution_result,
    execute_control_signals,
    execute_with_enforcement,
    explain_execution_path,
    summarize_execution_result,
    validate_execution_result,
)
from spectrum_systems.modules.runtime.control_signals import (  # noqa: E402
    derive_control_signals,
)
from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    run_control_chain,
)
from scripts.run_slo_control_chain import main as cc_main  # noqa: E402


def _base_signals(**overrides: Any) -> Dict[str, Any]:
    base = {
        "continuation_mode": "continue",
        "required_inputs": [],
        "required_validators": [],
        "repair_actions": [],
        "rerun_recommended": False,
        "human_review_required": False,
        "escalation_required": False,
        "publication_allowed": True,
        "decision_grade_allowed": True,
        "traceability_required": False,
        "control_signal_reason_codes": [],
    }
    base.update(overrides)
    return base


def _artifact() -> Dict[str, Any]:
    return {"artifact_id": "ART-001", "payload": {"x": 1}}


def _ctx(**overrides: Any) -> Dict[str, Any]:
    c = {"artifact": _artifact(), "stage": "synthesis", "runtime_environment": "test"}
    c.update(overrides)
    return c


def _evaluation() -> Dict[str, Any]:
    return {
        "evaluation_id": "EVAL-1",
        "artifact_id": "ART-001",
        "slo_status": "pass",
        "allowed_to_proceed": True,
        "slis": {"traceability_integrity": 1.0},
        "lineage_valid": True,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "parent_artifact_ids": ["PARENT-1"],
        "violations": [],
        "error_budget": 0.0,
        "inputs": {},
        "created_at": "2026-03-20T00:00:00+00:00",
    }


def test_continue_mode_executes_validators_and_proceeds():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "success"
    assert result["validators_run"] == ["validate_schema_conformance"]


def test_continue_with_monitoring_runs_validators_and_review():
    cs = _base_signals(
        continuation_mode="continue_with_monitoring",
        required_validators=["validate_schema_conformance"],
        human_review_required=True,
    )
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "success"
    assert result["human_review_required"] is True


def test_stop_blocks_execution_completely():
    result = execute_control_signals(_base_signals(continuation_mode="stop"), _ctx())
    assert result["execution_status"] == "blocked"


def test_stop_and_repair_emits_or_applies_repairs():
    cs = _base_signals(
        continuation_mode="stop_and_repair",
        repair_actions=["repair_schema_errors", "repair_missing_inputs"],
    )
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "repair_required"
    assert [r["repair_action"] for r in result["repair_actions_applied"]] == [
        "repair_schema_errors",
        "repair_missing_inputs",
    ]


def test_stop_and_rerun_triggers_rerun():
    cs = _base_signals(continuation_mode="stop_and_rerun")
    result = execute_control_signals(cs, _ctx())
    assert result["rerun_triggered"] is True
    assert result["execution_status"] == "blocked"


def test_stop_and_escalate_triggers_escalation_once():
    cs = _base_signals(continuation_mode="stop_and_escalate", escalation_required=True)
    result = execute_control_signals(cs, _ctx())
    escalation_actions = [a for a in result["actions_taken"] if a["action_type"] == "escalation_event_emitted"]
    assert result["execution_status"] == "escalated"
    assert len(escalation_actions) == 1


def test_missing_validator_fails_closed():
    cs = _base_signals(required_validators=["validate_not_registered"])
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "blocked"
    assert result["validators_failed"] == ["validate_not_registered"]


def test_publication_allowed_false_blocks_publication():
    result = execute_control_signals(_base_signals(publication_allowed=False), _ctx())
    assert result["publication_blocked"] is True
    assert result["execution_status"] == "blocked"


def test_decision_grade_false_blocks_decision_use():
    result = execute_control_signals(_base_signals(decision_grade_allowed=False), _ctx())
    assert result["decision_blocked"] is True
    assert result["execution_status"] == "blocked"


def test_validators_run_in_deterministic_order():
    validators = ["validate_schema_conformance", "validate_traceability_integrity"]
    result = execute_control_signals(_base_signals(required_validators=validators), _ctx())
    assert result["validators_run"] == validators


def test_repair_actions_are_deterministic():
    actions = ["repair_missing_inputs", "repair_schema_errors"]
    result = execute_control_signals(_base_signals(continuation_mode="stop_and_repair", repair_actions=actions), _ctx())
    assert [a["repair_action"] for a in result["repair_actions_applied"]] == actions


def test_human_review_event_emitted_when_required():
    result = execute_control_signals(_base_signals(human_review_required=True), _ctx())
    review_actions = [a for a in result["actions_taken"] if a["action_type"] == "human_review_required"]
    assert len(review_actions) == 1


def test_execution_result_schema_validation():
    result = execute_control_signals(_base_signals(), _ctx())
    assert validate_execution_result(result) == []


def test_control_chain_integration_execute_flag_adds_execution_result():
    result = run_control_chain(_evaluation(), stage="synthesis", execute=True)
    assert "execution_result" in result


def test_cli_execute_prints_execution_summary(capsys):
    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / "evaluation.json"
        output_path = Path(td) / "decision.json"
        input_path.write_text(json.dumps(_evaluation()), encoding="utf-8")
        code = cc_main([str(input_path), "--stage", "synthesis", "--execute", "--output", str(output_path)])
        out = capsys.readouterr().out
    assert code in {0, 1, 2}
    assert "Control Execution Result (BN.6)" in out


def test_no_contradiction_between_signals_and_execution_result():
    cs = derive_control_signals(
        continuation_allowed=False,
        primary_reason_code="control_chain_blocked_by_gating",
        gating_outcome="halt",
        enforcement_status="fail",
        lineage_defaulted=False,
        lineage_valid=False,
        stage="synthesis",
    )
    result = execute_control_signals(cs, _ctx())
    assert cs["continuation_mode"].startswith("stop")
    assert result["execution_status"] in {"blocked", "repair_required", "escalated"}


def test_execution_result_consistent_across_repeated_runs():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    first = execute_control_signals(cs, _ctx(trace_id="11111111-1111-4111-8111-111111111111", run_id="run-fixed"))
    second = execute_control_signals(cs, _ctx(trace_id="11111111-1111-4111-8111-111111111111", run_id="run-fixed"))
    assert first == second


def test_partial_failure_does_not_allow_continuation():
    cs = _base_signals(required_validators=["validate_schema_conformance", "validate_missing"])
    result = execute_control_signals(cs, _ctx())
    assert result["validators_failed"]
    assert result["execution_status"] == "blocked"


def test_repair_and_rerun_combination_blocked_and_rerun_true():
    cs = _base_signals(
        continuation_mode="stop_and_rerun",
        repair_actions=["repair_missing_inputs"],
    )
    result = execute_control_signals(cs, _ctx())
    assert result["rerun_triggered"] is True
    assert result["execution_status"] == "blocked"


def test_blocked_state_never_allows_publication_when_disallowed():
    cs = _base_signals(continuation_mode="stop", publication_allowed=False)
    result = execute_control_signals(cs, _ctx())
    assert result["publication_blocked"] is True


def test_execution_does_not_mutate_inputs():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    original = copy.deepcopy(cs)
    execute_control_signals(cs, _ctx())
    assert cs == original


def test_execution_is_idempotent():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    first = execute_control_signals(cs, _ctx(trace_id="22222222-2222-4222-8222-222222222222", run_id="run-fixed"))
    second = execute_control_signals(cs, _ctx(trace_id="22222222-2222-4222-8222-222222222222", run_id="run-fixed"))
    assert first == second


def test_missing_control_signals_fails_closed():
    result = execute_control_signals(None, _ctx())
    assert result["execution_status"] == "blocked"
    assert result["publication_blocked"] is True


def test_summary_and_path_diagnostics_are_structured():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    result = execute_control_signals(cs, _ctx())
    summary = summarize_execution_result(result)
    path = explain_execution_path(cs, result)
    assert "execution_status" in summary
    assert path["continuation_mode"] == cs["continuation_mode"]


def test_build_execution_result_helper_contract_shape():
    artifact = build_execution_result(
        execution_status="success",
        actions_taken=[],
        validators_run=[],
        validators_failed=[],
        repair_actions_applied=[],
        publication_blocked=False,
        decision_blocked=False,
        rerun_triggered=False,
        escalation_triggered=False,
        human_review_required=False,
        trace_id="trace-001",
        run_id="run-001",
        artifact_id="ART-001",
    )
    assert validate_execution_result(artifact) == []


def test_trace_emission_failure_blocks_execution(monkeypatch):
    import spectrum_systems.modules.runtime.control_executor as ce

    def _raise(*_args, **_kwargs):
        raise ce.TraceNotFoundError("missing trace")

    monkeypatch.setattr(ce, "validate_trace_context", lambda _trace_id: [])
    monkeypatch.setattr(ce, "start_span", _raise)
    result = execute_control_signals(_base_signals(), _ctx(trace_id="33333333-3333-4333-8333-333333333333"))
    assert result["execution_status"] == "blocked"
    assert result["actions_taken"][0]["action_type"] == "observability_emission_failed"


def test_control_execution_result_requires_correlation_keys():
    result = execute_control_signals(_base_signals(), _ctx(trace_id="trace-002"))
    assert result["trace_id"] == "trace-002"
    assert result["run_id"]
    assert result["artifact_id"] == "ART-001"


def test_execute_with_enforcement_uses_canonical_enforcement_path(monkeypatch):
    import spectrum_systems.modules.runtime.control_executor as ce

    decision = {
        "artifact_type": "evaluation_control_decision",
        "schema_version": "1.2.0",
        "decision_id": "ecd-1",
        "eval_run_id": "eval-run-1",
        "system_status": "healthy",
        "system_response": "allow",
        "triggered_signals": [],
        "threshold_snapshot": {
            "reliability_threshold": 0.85,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
        "threshold_context": "active_runtime",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "created_at": "2026-04-08T00:00:00Z",
        "decision": "allow",
        "rationale_code": "allow_healthy_eval_summary",
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": "eval-run-1",
        },
        "run_id": "eval-run-1",
    }
    expected = {
        "artifact_type": "enforcement_result",
        "schema_version": "1.1.0",
        "enforcement_result_id": "ENF-test",
        "timestamp": "2026-04-08T00:00:01Z",
        "trace_id": decision["trace_id"],
        "run_id": decision["run_id"],
        "input_decision_reference": decision["decision_id"],
        "enforcement_action": "allow_execution",
        "final_status": "allow",
        "rationale_code": decision["rationale_code"],
        "fail_closed": False,
        "enforcement_path": "baf_single_path",
        "provenance": {
            "source_artifact_type": "evaluation_control_decision",
            "source_artifact_id": decision["decision_id"],
        },
    }

    monkeypatch.setattr(ce, "validate_and_emit_decision", lambda _bundle_path: decision)
    monkeypatch.setattr(ce, "enforce_control_decision", lambda payload: expected if payload is decision else {})

    assert execute_with_enforcement("bundle-path") == expected
