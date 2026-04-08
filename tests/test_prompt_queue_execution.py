"""Tests for governed prompt queue controlled execution MVP."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ExecutionQueueIntegrationError,
    ExecutionRunnerError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    finalize_execution,
    make_queue_state,
    make_work_item,
    revalidate_execution_entry,
    run_live_execution,
    run_simulated_execution,
    transition_to_executing,
    validate_execution_result_artifact,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.execution_artifact_io import write_execution_result_artifact  # noqa: E402


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _runnable_item() -> dict:
    item = make_work_item(
        work_item_id="wi-parent.repair.1",
        prompt_id="prompt-parent:repair:1",
        title="Repair child",
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/execution",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent",
        clock=FixedClock(["2026-03-22T02:00:00Z"]),
    )
    item["status"] = WorkItemStatus.RUNNABLE.value
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    item["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-parent.findings.json"
    item["spawned_from_review_artifact_path"] = "docs/reviews/2026-03-22-parent-review.md"
    item["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json"
    return item


def _permission_decision(*, decision: str = "allow", producer: str = "permission_governance") -> dict:
    record = load_example("permission_decision_record")
    record["workflow_id"] = "queue-01"
    record["decision"] = decision
    record["trace"]["trace_refs"] = ["queue_id:queue-01", "work_item_id:wi-parent.repair.1", "step_id:step-001"]
    record["provenance"]["producer"] = producer
    return record


def _queue(item: dict) -> dict:
    return make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T02:00:00Z"]))


def test_valid_runnable_work_item_executes_successfully(tmp_path: Path):
    item = _runnable_item()
    queue = _queue(item)
    decision = _permission_decision()
    revalidate_execution_entry(work_item=item, permission_decision_record=decision, human_checkpoint_decision=None)
    queue_executing, executing_item = transition_to_executing(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        clock=FixedClock(["2026-03-22T02:00:01Z", "2026-03-22T02:00:02Z"]),
    )
    result = run_simulated_execution(
        work_item=executing_item,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T02:00:03Z", "2026-03-22T02:00:04Z"]),
    )
    validate_execution_result_artifact(result)
    result_path = tmp_path / "execution_results" / "wi-parent.repair.1.execution_result.json"
    write_execution_result_artifact(result, result_path)

    queue_final, updated_item = finalize_execution(
        queue_state=queue_executing,
        work_item_id=item["work_item_id"],
        execution_result_artifact_path=str(result_path),
        execution_status=result["execution_status"],
        clock=FixedClock(["2026-03-22T02:00:05Z", "2026-03-22T02:00:06Z"]),
    )

    assert updated_item["status"] == WorkItemStatus.EXECUTED_SUCCESS.value
    assert updated_item["execution_result_artifact_path"] == str(result_path)
    validate_work_item(updated_item)
    validate_queue_state(queue_final)


def test_execution_fails_closed_if_gating_path_missing():
    item = _runnable_item()
    item["gating_decision_artifact_path"] = None
    revalidate_execution_entry(
        work_item=item,
        permission_decision_record=_permission_decision(),
        human_checkpoint_decision=None,
    )


def test_execution_fails_closed_if_permission_artifact_schema_invalid():
    item = _runnable_item()
    invalid = _permission_decision()
    invalid.pop("decision")
    with pytest.raises(ExecutionRunnerError):
        revalidate_execution_entry(work_item=item, permission_decision_record=invalid, human_checkpoint_decision=None)


def test_execution_fails_closed_if_permission_decision_not_allow():
    item = _runnable_item()
    denied = _permission_decision(decision="deny")
    with pytest.raises(ExecutionRunnerError, match="must allow execution"):
        revalidate_execution_entry(work_item=item, permission_decision_record=denied, human_checkpoint_decision=None)


def test_duplicate_execution_prevented_once_item_is_not_runnable():
    item = _runnable_item()
    queue = _queue(item)
    queue_executing, _ = transition_to_executing(queue_state=queue, work_item_id=item["work_item_id"])
    queue_final, _ = finalize_execution(
        queue_state=queue_executing,
        work_item_id=item["work_item_id"],
        execution_result_artifact_path="artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json",
        execution_status="success",
    )

    with pytest.raises(ExecutionQueueIntegrationError, match="Duplicate execution prevented"):
        transition_to_executing(queue_state=queue_final, work_item_id=item["work_item_id"])


def test_wrong_starting_state_fails_closed():
    item = _runnable_item()
    item["status"] = WorkItemStatus.EXECUTION_GATED.value
    with pytest.raises(ExecutionRunnerError, match="status 'runnable'"):
        revalidate_execution_entry(work_item=item, permission_decision_record=_permission_decision(), human_checkpoint_decision=None)


def test_execution_result_artifact_validates_against_schema():
    validate_execution_result_artifact(load_example("prompt_queue_execution_result"))


def test_live_execution_writes_real_output_artifact(tmp_path: Path):
    item = _runnable_item()
    item["status"] = WorkItemStatus.EXECUTING.value
    result = run_live_execution(
        work_item=item,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        live_output_root=str(tmp_path / "live_outputs"),
        clock=FixedClock(["2026-03-22T03:30:00Z", "2026-03-22T03:30:01Z"]),
    )
    validate_execution_result_artifact(result)
    assert result["execution_mode"] == "live"
    assert result["execution_status"] == "success"
    output_path = Path(result["output_reference"])
    assert output_path.is_file()
    payload = output_path.read_text(encoding="utf-8")
    assert "\"execution_mode\": \"live\"" in payload


def test_live_execution_without_output_root_fails_closed():
    item = _runnable_item()
    item["status"] = WorkItemStatus.EXECUTING.value
    with pytest.raises(ExecutionRunnerError, match="live output root"):
        run_live_execution(
            work_item=item,
            source_queue_state_path="artifacts/prompt_queue/queue_state.json",
            live_output_root=None,
            clock=FixedClock(["2026-03-22T03:31:00Z", "2026-03-22T03:31:01Z"]),
        )


def test_deterministic_simulated_execution_same_input_same_result():
    item = _runnable_item()
    item["status"] = WorkItemStatus.EXECUTING.value
    first = run_simulated_execution(
        work_item=item,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:00:00Z", "2026-03-22T03:00:01Z"]),
    )
    second = run_simulated_execution(
        work_item=item,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:00:00Z", "2026-03-22T03:00:01Z"]),
    )
    assert first == second


def test_partial_failure_artifact_written_but_queue_finalization_fails_blocks_second_execution(tmp_path: Path):
    item = _runnable_item()
    queue = _queue(item)
    revalidate_execution_entry(work_item=item, permission_decision_record=_permission_decision(), human_checkpoint_decision=None)
    queue_executing, executing_item = transition_to_executing(queue_state=queue, work_item_id=item["work_item_id"])

    result = run_simulated_execution(
        work_item=executing_item,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T04:00:00Z", "2026-03-22T04:00:01Z"]),
    )
    result_path = tmp_path / "execution_results" / "wi-parent.repair.1.execution_result.json"
    write_execution_result_artifact(result, result_path)

    with pytest.raises(ExecutionQueueIntegrationError, match="status 'executing'"):
        finalize_execution(
            queue_state=queue,
            work_item_id=item["work_item_id"],
            execution_result_artifact_path=str(result_path),
            execution_status=result["execution_status"],
        )

    with pytest.raises(ExecutionQueueIntegrationError, match="requires work item status 'runnable'"):
        transition_to_executing(queue_state=queue_executing, work_item_id=item["work_item_id"])


def test_updated_queue_and_work_item_validate_after_execution():
    item = _runnable_item()
    queue = _queue(item)

    queue_executing, executing_item = transition_to_executing(queue_state=queue, work_item_id=item["work_item_id"])
    result = run_simulated_execution(
        work_item=executing_item,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T05:00:00Z", "2026-03-22T05:00:01Z"]),
    )

    queue_final, updated_item = finalize_execution(
        queue_state=queue_executing,
        work_item_id=item["work_item_id"],
        execution_result_artifact_path="artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json",
        execution_status=result["execution_status"],
    )

    validate_work_item(updated_item)
    validate_queue_state(queue_final)


def test_execution_requires_approved_checkpoint_for_approval_required_decision():
    item = _runnable_item()
    decision = _permission_decision(decision="require_human_approval")

    with pytest.raises(ExecutionRunnerError, match="human checkpoint decision is required"):
        revalidate_execution_entry(work_item=item, permission_decision_record=decision, human_checkpoint_decision=None)

    with pytest.raises(ExecutionRunnerError, match="blocked progression"):
        revalidate_execution_entry(
            work_item=item,
            permission_decision_record=decision,
            human_checkpoint_decision=load_example("human_checkpoint_decision") | {"decision": "reject"},
        )


def test_execution_accepts_approval_required_with_approve_checkpoint():
    item = _runnable_item()
    decision = _permission_decision(decision="require_human_approval")
    checkpoint = load_example("human_checkpoint_decision")
    checkpoint["decision"] = "approve"
    checkpoint["request_id"] = "hcr-r-3"
    revalidate_execution_entry(work_item=item, permission_decision_record=decision, human_checkpoint_decision=checkpoint)
