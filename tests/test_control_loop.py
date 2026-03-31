from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.control_loop import (  # noqa: E402
    ControlLoopError,
    aggregate_error_budget_window,
    run_control_loop,
    run_judgment_learning_control_loop,
)
from spectrum_systems.modules.runtime.evaluation_auto_generation import (  # noqa: E402
    generate_failure_eval_case,
    register_failure_eval_case,
)


def _trace_context(replay: Dict[str, Any] | None = None) -> Dict[str, Any]:
    replay = replay or _replay_result()
    return {
        "execution_id": "exec-001",
        "stage": "synthesis",
        "runtime_environment": "test",
        "trace_id": replay["trace_id"],
        "replay_id": replay["replay_id"],
        "replay_run_id": replay["replay_run_id"],
    }


def _replay_result() -> Dict[str, Any]:
    replay = copy.deepcopy(load_example("replay_result"))
    replay.setdefault("observability_metrics", {}).setdefault("metrics", {})["drift_exceed_threshold_rate"] = 0.0
    return replay


def _failure_eval_case() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    failure_eval = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-loop-001",
            "trace_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        },
        source_run_id="run-loop-001",
        stage="control",
        runtime_environment="test",
        execution_result={"continuation_allowed": False, "publication_blocked": True, "decision_blocked": True},
    )
    registry: dict[str, dict[str, Any]] = {}
    register_failure_eval_case(
        failure_eval_case=failure_eval,
        eval_registry=registry,
        policy_id="failure-binding-policy-v1",
        trigger_condition="on_failure_record_emitted",
    )
    trace_context = {"trace_id": failure_eval["trace_id"], "failure_eval_registry": registry}
    return failure_eval, registry, trace_context


def test_replay_result_allow_path() -> None:
    result = run_control_loop(_replay_result(), _trace_context())
    assert result["control_trace"]["signal_type"] == "replay_result"
    assert result["control_trace"]["evaluation_path"] == "evaluation_control_from_replay_result"


def test_non_replay_artifact_rejected() -> None:
    with pytest.raises(ControlLoopError, match="unsupported artifact_type"):
        run_control_loop({"artifact_type": "unknown"}, _trace_context())


def test_partial_replay_rejected() -> None:
    replay = _replay_result()
    replay.pop("error_budget_status")
    with pytest.raises(ControlLoopError, match="normalized signal missing required field"):
        run_control_loop(replay, _trace_context())


def test_budget_exhausted_forces_block_or_freeze() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "exhausted"
    replay["error_budget_status"]["highest_severity"] = "exhausted"
    replay["error_budget_status"]["triggered_conditions"] = [
        {
            "metric_name": "replay_success_rate",
            "status": "exhausted",
            "consumption_ratio": 1.0,
        }
    ]
    decision = run_control_loop(replay, _trace_context(replay))["evaluation_control_decision"]
    assert decision["system_response"] in {"block", "freeze"}


def test_budget_warning_forces_warn() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "warning"
    replay["error_budget_status"]["highest_severity"] = "warning"
    replay["error_budget_status"]["triggered_conditions"] = [
        {
            "metric_name": "replay_success_rate",
            "status": "warning",
            "consumption_ratio": 0.9,
        }
    ]
    decision = run_control_loop(replay, _trace_context(replay))["evaluation_control_decision"]
    assert decision["system_response"] == "warn"


def test_control_loop_uses_budget() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "warning"
    replay["error_budget_status"]["highest_severity"] = "warning"
    replay["error_budget_status"]["triggered_conditions"] = [
        {"metric_name": "replay_success_rate", "status": "warning", "consumption_ratio": 0.7}
    ]
    decision = run_control_loop(replay, _trace_context(replay))["evaluation_control_decision"]
    assert "budget_warning" in decision["triggered_signals"]
    assert decision["decision"] == "require_review"


def test_budget_observability_mismatch_fails_closed() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["objectives"][0]["observed_value"] = 0.01
    with pytest.raises(ControlLoopError, match="inconsistent replay_result observability_metrics vs error_budget_status"):
        run_control_loop(replay, _trace_context(replay))


def test_budget_observability_small_float_delta_is_tolerated() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["objectives"][0]["observed_value"] = (
        replay["observability_metrics"]["metrics"]["replay_success_rate"] - 1e-7
    )
    decision = run_control_loop(replay, _trace_context(replay))["evaluation_control_decision"]
    assert decision["system_response"] in {"allow", "warn", "freeze", "block"}


def test_decision_deterministic_for_identical_replay_input() -> None:
    replay = _replay_result()
    first = run_control_loop(replay, _trace_context())["evaluation_control_decision"]
    second = run_control_loop(copy.deepcopy(replay), _trace_context())["evaluation_control_decision"]
    assert first["decision_id"] == second["decision_id"]


def test_trace_context_replay_identity_aligned_passes() -> None:
    replay = _replay_result()
    result = run_control_loop(replay, _trace_context(replay))
    assert result["control_trace"]["input_artifact_id"] == replay["replay_id"]


def test_trace_context_replay_identity_mismatch_fail_closed() -> None:
    replay = _replay_result()
    trace_context = _trace_context(replay)
    trace_context["replay_id"] = "RPL-mismatch"
    with pytest.raises(ControlLoopError, match="trace_context linkage mismatch for replay_id"):
        run_control_loop(replay, trace_context)


def test_trace_context_missing_required_trace_linkage_fail_closed() -> None:
    replay = _replay_result()
    trace_context = _trace_context(replay)
    trace_context.pop("trace_id")
    with pytest.raises(ControlLoopError, match="trace_context missing required linkage field: trace_id"):
        run_control_loop(replay, trace_context)


def test_rolling_window_aggregation_returns_deterministic_budget_summary() -> None:
    replay = _replay_result()
    exhausted = _replay_result()
    exhausted["replay_run_id"] = "eval-run-002"
    exhausted["timestamp"] = "2026-03-22T00:01:00Z"
    exhausted["error_budget_status"]["budget_status"] = "exhausted"
    exhausted["error_budget_status"]["highest_severity"] = "exhausted"
    summary = aggregate_error_budget_window([replay, exhausted], last_n_runs=2)
    assert summary["aggregated_budget_status"] == "exhausted"
    assert summary["window_size"] == 2


def test_budget_status_more_severe_than_highest_severity_fails_closed() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "exhausted"
    replay["error_budget_status"]["highest_severity"] = "warning"
    with pytest.raises(ControlLoopError, match="budget_status exceeds highest_severity"):
        run_control_loop(replay, _trace_context(replay))


def test_error_budget_schema_delegation_rejects_invalid_objective_status() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["objectives"][0]["status"] = "not-a-valid-status"
    with pytest.raises(ControlLoopError, match="error_budget_status failed validation"):
        run_control_loop(replay, _trace_context(replay))


def test_missing_budget_evaluation_blocks() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["objectives"] = []
    with pytest.raises(ControlLoopError, match="error_budget_status failed validation"):
        run_control_loop(replay, _trace_context(replay))


def test_control_loop_uses_failure_eval() -> None:
    failure_eval, _, trace_context = _failure_eval_case()
    result = run_control_loop(failure_eval, trace_context)
    assert result["control_trace"]["signal_type"] == "failure_eval_case"
    assert result["control_trace"]["evaluation_path"] == "evaluation_control_from_failure_eval_case"
    assert result["evaluation_control_decision"]["decision"] in {"deny", "require_review"}


def test_missing_binding_blocks_execution() -> None:
    failure_eval, _, trace_context = _failure_eval_case()
    trace_context["failure_eval_registry"] = {}
    with pytest.raises(ControlLoopError, match="not registered in failure_eval_registry"):
        run_control_loop(failure_eval, trace_context)


def test_prevention_without_control_consumption_fails() -> None:
    failure_eval, registry, trace_context = _failure_eval_case()
    registry[failure_eval["eval_case_id"]].pop("recurrence_prevention_artifact")
    with pytest.raises(ControlLoopError, match="recurrence_prevention_artifact"):
        run_control_loop(failure_eval, trace_context)


def test_repeat_failure_changes_control_decision() -> None:
    failure_eval, registry, trace_context = _failure_eval_case()
    registry[failure_eval["eval_case_id"]]["recurrence_count"] = 3
    decision = run_control_loop(failure_eval, trace_context)["evaluation_control_decision"]
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "block"


def _judgment_learning_inputs() -> dict[str, Any]:
    drift = load_example("judgment_drift_signal")
    drift["group_signals"][0]["deltas"] = {
        "approval_rate_delta": 0.01,
        "block_rate_delta": 0.01,
        "error_rate_delta": 0.01,
        "calibration_ece_delta": 0.01,
    }
    drift["group_signals"][0]["drift_detected"] = False
    calibration = load_example("judgment_calibration_result")
    calibration["group_metrics"][0]["expected_calibration_error"] = 0.02
    return {
        "judgment_eval_result": load_example("judgment_eval_result"),
        "judgment_calibration_result": calibration,
        "judgment_drift_signal": drift,
        "judgment_error_budget_status": load_example("judgment_error_budget_status"),
        "judgment_policy": load_example("judgment_policy"),
        "trace_context": {"trace_id": "trace-001", "replay_run_id": "run-001"},
        "created_at": "2026-03-30T00:10:00Z",
    }


def test_judgment_learning_control_happy_path_allow() -> None:
    inputs = _judgment_learning_inputs()
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "allow"


def test_judgment_learning_control_blocks_when_error_budget_exhausted() -> None:
    inputs = _judgment_learning_inputs()
    inputs["judgment_error_budget_status"]["status"] = "exhausted"
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "block"


def test_judgment_learning_control_blocks_on_critical_drift() -> None:
    inputs = _judgment_learning_inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.2
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "block"


def test_judgment_learning_control_freezes_on_warning_drift() -> None:
    inputs = _judgment_learning_inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "freeze"


def test_judgment_learning_control_warns_on_rising_override_rate() -> None:
    inputs = _judgment_learning_inputs()
    inputs["judgment_error_budget_status"]["group_statuses"][0]["rates"]["override_rate"] = 0.2
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "warn"


def test_judgment_learning_control_fail_closed_missing_calibration_blocks() -> None:
    inputs = _judgment_learning_inputs()
    inputs["judgment_calibration_result"] = None
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "block"


def test_judgment_learning_control_deterministic_for_identical_inputs() -> None:
    inputs = _judgment_learning_inputs()
    first = run_judgment_learning_control_loop(**inputs)
    second = run_judgment_learning_control_loop(**copy.deepcopy(inputs))
    assert first == second


def test_judgment_learning_control_propagates_policy_lifecycle_linkage_to_enforcement() -> None:
    inputs = _judgment_learning_inputs()
    inputs["judgment_policy"]["status"] = "active"
    inputs["judgment_policy"]["artifact_version"] = "1.2.0"
    inputs["judgment_policy"]["_selected_rollout_id"] = "none"
    result = run_judgment_learning_control_loop(**inputs)

    escalation = result["judgment_control_escalation_record"]
    action = result["judgment_enforcement_action_record"]
    outcome = result["judgment_enforcement_outcome_record"]

    assert escalation["trace"]["judgment_policy_version"] == "1.2.0"
    assert escalation["trace"]["policy_lifecycle_status"] == "active"
    assert action["policy_refs"]["judgment_policy_version"] == "1.2.0"
    assert action["policy_refs"]["policy_lifecycle_status"] == "active"
    assert outcome["trace"]["judgment_policy_version"] == "1.2.0"
