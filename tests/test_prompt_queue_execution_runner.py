"""Tests for normalized prompt queue step execution runner adapter."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.pqx_execution_authority import issue_pqx_execution_authority_record  # noqa: E402
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


def _permission_decision(*, decision: str = "allow", producer: str = "permission_governance") -> dict:
    record = load_example("permission_decision_record")
    record["decision_id"] = "pdr-wi-q2-001"
    record["request_id"] = "req-wi-q2-001"
    record["workflow_id"] = "queue-q2"
    record["decision"] = decision
    record["trace"]["trace_refs"] = ["queue_id:queue-q2", "work_item_id:wi-q2-001", "step_id:step-001"]
    record["provenance"]["producer"] = producer
    return record


def _permission_request() -> dict:
    record = load_example("permission_request_record")
    record["request_id"] = "req-wi-q2-001"
    record["workflow_id"] = "queue-q2"
    return record


def _pqx_proof() -> dict:
    return issue_pqx_execution_authority_record(
        queue_id="queue-q2",
        work_item_id="wi-q2-001",
        step_id="step-001",
        trace={"trace_id": "queue-q2", "trace_refs": ["queue_id:queue-q2", "work_item_id:wi-q2-001", "step_id:step-001"]},
        source_refs=["permission_request_record:req-wi-q2-001", "permission_decision_record:pdr-wi-q2-001"],
    )


def test_valid_step_execution_produces_normalized_artifact():
    result = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
        queue_state=_queue(_work_item()),
        input_refs={
            "permission_request_record": _permission_request(),
            "permission_decision_record": _permission_decision(),
            "pqx_execution_authority_record": _pqx_proof(),
            "source_queue_state_path": "artifacts/prompt_queue/queue_state.json",
        },
        clock=FixedClock(["2026-03-28T00:00:01Z", "2026-03-28T00:00:02Z"]),
    )
    assert result["step_id"] == "step-001"
    assert result["queue_id"] == "queue-q2"
    assert result["execution_type"] == "queue_step"
    assert result["execution_mode"] == "simulated"
    assert result["produced_artifact_refs"] == ["artifacts/prompt_queue/simulated_outputs/wi-q2-001.output.json"]
    validate_execution_result_artifact(result)


def test_missing_required_step_fields_fail_closed():
    with pytest.raises(ExecutionRunnerError, match="step_id"):
        run_queue_step_execution(
            step={"work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": _permission_decision(),
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )


def test_malformed_input_refs_fail_closed():
    with pytest.raises(ExecutionRunnerError, match="Malformed input_refs"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={"permission_decision_record": "bad"},
        )


def test_missing_execution_mode_fails_closed():
    with pytest.raises(ExecutionRunnerError, match="execution_mode"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": _permission_decision(),
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )


def test_unknown_execution_shape_fails_closed():
    with pytest.raises(ExecutionRunnerError, match="Unknown execution shape"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "shadow"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": _permission_decision(),
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )


def test_live_mode_requires_live_output_root_fail_closed():
    with pytest.raises(ExecutionRunnerError, match="live output root"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "live"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": _permission_decision(),
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )


def test_live_mode_executes_with_real_output(tmp_path: Path):
    result = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "live"},
        queue_state=_queue(_work_item()),
        input_refs={
            "permission_request_record": _permission_request(),
            "permission_decision_record": _permission_decision(),
            "pqx_execution_authority_record": _pqx_proof(),
            "source_queue_state_path": "artifacts/prompt_queue/queue_state.json",
            "live_output_root": str(tmp_path / "live_outputs"),
        },
        clock=FixedClock(["2026-03-28T00:00:03Z", "2026-03-28T00:00:04Z"]),
    )
    assert result["execution_mode"] == "live"
    assert result["execution_status"] == "success"
    assert Path(result["output_reference"]).is_file()
    validate_execution_result_artifact(result)


def test_produced_artifact_refs_deterministic_for_same_input():
    queue_state = _queue(_work_item())
    refs = {
        "permission_request_record": _permission_request(),
        "permission_decision_record": _permission_decision(),
        "pqx_execution_authority_record": _pqx_proof(),
        "source_queue_state_path": "artifacts/prompt_queue/queue_state.json",
    }
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


def test_rejects_noncanonical_permission_provenance():
    with pytest.raises(ExecutionRunnerError, match="provenance"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": _permission_decision(producer="other_component"),
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )


def test_rejects_mismatched_work_item_trace_ref():
    bad = _permission_decision()
    bad["trace"]["trace_refs"] = ["work_item_id:wrong-id"]
    with pytest.raises(ExecutionRunnerError, match="work item"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": bad,
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )


def test_rejects_denied_permission_decision():
    with pytest.raises(ExecutionRunnerError, match="must allow execution"):
        run_queue_step_execution(
            step={"step_id": "step-001", "work_item_id": "wi-q2-001", "execution_mode": "simulated"},
            queue_state=_queue(_work_item()),
            input_refs={
                "permission_request_record": _permission_request(),
                "permission_decision_record": _permission_decision(decision="deny"),
                "pqx_execution_authority_record": _pqx_proof(),
            },
        )
