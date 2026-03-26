from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_control import (  # noqa: E402
    EvaluationControlError,
    build_evaluation_control_decision,
)


def _replay_result() -> dict:
    return copy.deepcopy(load_example("replay_result"))


def test_replay_result_healthy_allows() -> None:
    decision = build_evaluation_control_decision(_replay_result())
    assert decision["system_response"] == "allow"
    assert decision["decision"] == "allow"


def test_replay_result_with_explicit_drift_metric_is_supported() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.0
    decision = build_evaluation_control_decision(replay)
    assert decision["system_response"] == "allow"
    assert decision["decision"] == "allow"


def test_non_replay_input_fails_closed() -> None:
    with pytest.raises(EvaluationControlError, match="failed validation"):
        build_evaluation_control_decision({"artifact_type": "eval_summary"})


def test_partial_replay_without_observability_fails_closed() -> None:
    replay = _replay_result()
    replay.pop("observability_metrics")
    with pytest.raises(EvaluationControlError, match="must embed observability_metrics"):
        build_evaluation_control_decision(replay)


def test_partial_replay_without_error_budget_fails_closed() -> None:
    replay = _replay_result()
    replay.pop("error_budget_status")
    with pytest.raises(EvaluationControlError, match="must embed error_budget_status"):
        build_evaluation_control_decision(replay)


def test_invalid_trace_linkage_fails_closed() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["trace_refs"]["trace_id"] = "trace-mismatch"
    with pytest.raises(EvaluationControlError, match="REPLAY_INVALID_TRACE_LINKAGE"):
        build_evaluation_control_decision(replay)


def test_decision_id_is_deterministic_for_identical_replay_inputs() -> None:
    replay = _replay_result()
    first = build_evaluation_control_decision(replay)
    second = build_evaluation_control_decision(copy.deepcopy(replay))
    assert first["decision_id"] == second["decision_id"]


def test_missing_optional_drift_metric_is_deterministic() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["metrics"].pop("drift_exceed_threshold_rate", None)
    first = build_evaluation_control_decision(replay)
    second = build_evaluation_control_decision(copy.deepcopy(replay))
    assert first["decision_id"] == second["decision_id"]


def test_explicit_drift_metric_is_deterministic() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.0
    first = build_evaluation_control_decision(replay)
    second = build_evaluation_control_decision(copy.deepcopy(replay))
    assert first["decision_id"] == second["decision_id"]
