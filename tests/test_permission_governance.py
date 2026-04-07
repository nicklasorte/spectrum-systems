from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.permission_governance import (
    PermissionGovernanceError,
    evaluate_permission_decision,
    require_checkpoint_decision,
)


def _stage_contract() -> dict:
    return json.loads(
        (Path(__file__).resolve().parents[1] / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json").read_text(encoding="utf-8")
    )


def test_allow_path_emits_canonical_permission_artifacts() -> None:
    contract = _stage_contract()
    contract["permissions"]["tool_allowlist"] = ["python"]
    contract["permissions"]["write_scope"] = ["artifacts/pqx/"]
    result = evaluate_permission_decision(
        workflow_id="wf-1",
        stage_contract=contract,
        action_name="execute_tool",
        tool_name="python",
        resource_scope="write:artifacts/pqx/run-1",
        request_id="r-1",
        trace_id="trace-1",
    )
    assert result.permission_decision_record["artifact_type"] == "permission_decision_record"
    assert result.permission_decision_record["decision"] == "allow"
    assert result.human_checkpoint_request is None


def test_deny_path_blocks_deterministically() -> None:
    contract = _stage_contract()
    result = evaluate_permission_decision(
        workflow_id="wf-2",
        stage_contract=contract,
        action_name="execute_tool",
        tool_name="not_allowed",
        resource_scope="write:outside/root",
        request_id="r-2",
        trace_id="trace-2",
    )
    assert result.permission_decision_record["decision"] == "deny"
    assert "TOOL_NOT_ALLOWLISTED" in result.permission_decision_record["reason_codes"]


def test_require_human_approval_needs_approve_decision() -> None:
    contract = _stage_contract()
    contract["permissions"]["human_approval_required_for"] = ["execute_tool"]
    contract["permissions"]["tool_allowlist"] = ["python"]
    contract["permissions"]["write_scope"] = ["artifacts/pqx/"]
    result = evaluate_permission_decision(
        workflow_id="wf-3",
        stage_contract=contract,
        action_name="execute_tool",
        tool_name="python",
        resource_scope="write:artifacts/pqx/run-3",
        request_id="r-3",
        trace_id="trace-3",
    )
    assert result.permission_decision_record["decision"] == "require_human_approval"
    assert result.human_checkpoint_request is not None

    with pytest.raises(PermissionGovernanceError):
        require_checkpoint_decision(
            permission_decision_record=result.permission_decision_record,
            human_checkpoint_decision=None,
        )

    with pytest.raises(PermissionGovernanceError):
        require_checkpoint_decision(
            permission_decision_record=result.permission_decision_record,
            human_checkpoint_decision={
                "artifact_type": "human_checkpoint_decision",
                "schema_version": "1.0.0",
                "decision_id": "d-1",
                "request_id": result.human_checkpoint_request["request_id"],
                "reviewer_id": "r",
                "decision": "reject",
                "rationale": "no",
                "decided_at": "2026-04-07T00:00:00Z",
                "trace": {"trace_id": "trace-3", "trace_refs": []},
            },
        )
