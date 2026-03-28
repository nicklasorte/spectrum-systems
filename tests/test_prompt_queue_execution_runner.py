"""Tests for normalized prompt queue step execution runner adapter."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ExecutionRunnerError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    make_queue_state,
    make_work_item,
    run_queue_step_execution,
    validate_execution_result_artifact,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 28, 0, 0, 0, tzinfo=timezone.utc)


def _work_item() -> dict:
    item = make_work_item(
        work_item_id="wi-q2-001",
        prompt_id="prompt-q2-001",
        title="Q2 Execution",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="main",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
    )
    item["status"] = WorkItemStatus.RUNNABLE.value
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-q2.repair_prompt.json"
    item["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-q2.findings.json"
    item["spawned_from_review_artifact_path"] = "docs/reviews/2026-03-28-q2.md"
    item["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-q2.execution_gating_decision.json"
    return item


def _queue(item: dict) -> dict:
    return make_queue_state(queue_id="queue-q2", work_items=[item])


def _gating() -> dict:
    gating = load_example("prompt_queue_execution_gating_decision")
    gating["work_item_id"] = "wi-q2-001"
    gating["decision_status"] = "runnable"
    gating["decision_reason_code"] = "runnable_within_policy"
    return gating


def test_valid_step_execution_produces_normalized_artifact():
    result = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
        queue_state=_queue(_work_item()),
        input_refs={
            "gating_decision_artifact": _gating(),
            "source_queue_state_path": "artifacts/prompt_queue/queue_state.json",
        },
        clock=FixedClock(["2026-03-28T00:00:01Z", "2026-03-28T00:00:02Z"]),
    )
    assert result["step_id"] == "step-001"
    assert result["queue_id"] == "queue-q2"
    assert result["execution_type"] == "queue_step"
    assert result["produced_artifact_refs"] == ["artifacts/prompt_queue/simulated_outputs/wi-q2-001.output.json"]
    validate_execution_result_artifact(result)


def test_missing_required_step_fields_fail_closed():
    with pytest.raises(ExecutionRunnerError, match="step_id"):
        run_queue_step_execution(
            step={"work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={"gating_decision_artifact": _gating()},
        )


def test_malformed_input_refs_fail_closed():
    with pytest.raises(ExecutionRunnerError, match="Malformed input_refs"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={"gating_decision_artifact": "bad"},
        )


def test_unknown_execution_shape_fails_closed():
    with pytest.raises(ExecutionRunnerError, match="Unknown execution shape"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "live"},
            queue_state=_queue(_work_item()),
            input_refs={"gating_decision_artifact": _gating()},
        )


def test_produced_artifact_refs_deterministic_for_same_input():
    queue_state = _queue(_work_item())
    refs = {"gating_decision_artifact": _gating(), "source_queue_state_path": "artifacts/prompt_queue/queue_state.json"}
    first = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
        queue_state=queue_state,
        input_refs=refs,
        clock=FixedClock(["2026-03-28T00:00:01Z", "2026-03-28T00:00:02Z"]),
    )
    second = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
        queue_state=queue_state,
        input_refs=refs,
        clock=FixedClock(["2026-03-28T00:00:01Z", "2026-03-28T00:00:02Z"]),
    )
    assert first["produced_artifact_refs"] == second["produced_artifact_refs"]
