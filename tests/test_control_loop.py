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
