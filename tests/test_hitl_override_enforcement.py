from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.agent_golden_path import GoldenPathConfig, run_agent_golden_path


def _config(tmp_path: Path, **overrides: object) -> GoldenPathConfig:
    base = {
        "task_type": "meeting_minutes",
        "input_payload": {"transcript": "AG-04 deterministic runtime transcript"},
        "source_artifacts": [{"artifact_id": "artifact-001", "kind": "source"}],
        "context_config": {},
        "output_dir": tmp_path,
    }
    base.update(overrides)
    return GoldenPathConfig(**base)


def _make_override(
    *,
    review_request: dict,
    execution_record: dict,
    decision_status: str = "allow_once",
    allowed_next_action: str = "resume_once",
    review_role: str = "control_authority_reviewer",
) -> dict:
    return {
        "artifact_type": "hitl_override_decision",
        "schema_version": "1.0.0",
        "override_decision_id": "hod-runtime-test-001",
        "created_at": "2026-01-05T14:22:31Z",
        "trace_id": review_request["trace_id"],
        "review_request_id": review_request["id"],
        "related_execution_record_id": execution_record["artifact_id"],
        "decision_status": decision_status,
        "decision_reason": "Deterministic AG-04 enforcement test decision.",
        "decided_by": {"actor_id": "reviewer-001", "role": review_role},
        "decision_scope": "ag_runtime_review_boundary",
        "allowed_next_action": allowed_next_action,
        "trace_refs": {"primary": review_request["trace_id"], "related": [review_request["trace_id"]]},
        "related_artifact_refs": [
            f"hitl_review_request:{review_request['id']}",
            f"final_execution_record:{execution_record['artifact_id']}",
        ],
    }


def test_hitl_override_decision_example_validates() -> None:
    validate_artifact(load_example("hitl_override_decision"), "hitl_override_decision")


def test_missing_override_when_required_fails_closed(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, force_review_required=True, require_override_decision=True))

    action = artifacts["final_execution_record"]["actions_taken"][0]
    assert action["action_type"] == "hitl_override_enforcement_failed"
    assert action["reason"] == "override_missing"
    assert artifacts["final_execution_record"]["execution_status"] == "blocked"
    assert "enforcement" not in artifacts


def test_malformed_override_rejected(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not-json", encoding="utf-8")

    artifacts = run_agent_golden_path(
        _config(
            tmp_path,
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[bad_path],
        )
    )

    action = artifacts["final_execution_record"]["actions_taken"][0]
    assert action["action_type"] == "hitl_override_enforcement_failed"
    assert action["reason"] == "override_malformed"
    assert "enforcement" not in artifacts


def test_invalid_override_schema_rejected(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid_override.json"
    invalid_path.write_text(json.dumps({"artifact_type": "hitl_override_decision"}, indent=2) + "\n", encoding="utf-8")

    artifacts = run_agent_golden_path(
        _config(
            tmp_path,
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[invalid_path],
        )
    )

    action = artifacts["final_execution_record"]["actions_taken"][0]
    assert action["action_type"] == "hitl_override_enforcement_failed"
    assert action["reason"] == "schema_error"
    assert "enforcement" not in artifacts


def test_incompatible_override_status_rejected(tmp_path: Path) -> None:
    preview = run_agent_golden_path(_config(tmp_path / "preview", force_review_required=True))
    payload = _make_override(
        review_request=preview["hitl_review_request"],
        execution_record=preview["final_execution_record"],
        decision_status="allow_once",
        allowed_next_action="remain_blocked",
    )
    path = tmp_path / "override_incompatible.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    artifacts = run_agent_golden_path(
        _config(
            tmp_path / "run",
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[path],
        )
    )

    action = artifacts["final_execution_record"]["actions_taken"][0]
    assert action["action_type"] == "hitl_override_enforcement_failed"
    assert action["reason"] == "override_incompatible"
    assert artifacts["final_execution_record"]["execution_status"] == "blocked"
    assert "control_decision" not in artifacts


def test_non_resume_override_does_not_leak_downstream_actions(tmp_path: Path) -> None:
    preview = run_agent_golden_path(_config(tmp_path / "preview", force_review_required=True))
    payload = _make_override(
        review_request=preview["hitl_review_request"],
        execution_record=preview["final_execution_record"],
        decision_status="require_rerun",
        allowed_next_action="rerun_from_context",
    )
    path = tmp_path / "override_rerun.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    artifacts = run_agent_golden_path(
        _config(
            tmp_path / "run",
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[path],
        )
    )

    assert artifacts["final_execution_record"]["execution_status"] == "repair_required"
    assert artifacts["final_execution_record"]["rerun_triggered"] is True
    assert "control_decision" not in artifacts
    assert "enforcement" not in artifacts


def test_deterministic_replay_with_override(tmp_path: Path) -> None:
    preview = run_agent_golden_path(_config(tmp_path / "preview", force_review_required=True))
    payload = _make_override(
        review_request=preview["hitl_review_request"],
        execution_record=preview["final_execution_record"],
    )
    path = tmp_path / "override.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    first = run_agent_golden_path(
        _config(
            tmp_path / "run1",
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[path],
        )
    )
    second = run_agent_golden_path(
        _config(
            tmp_path / "run2",
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[path],
        )
    )

    assert first["control_decision"]["decision_id"] == second["control_decision"]["decision_id"]
    assert first["enforcement"]["enforcement_result_id"] == second["enforcement"]["enforcement_result_id"]
    assert first["hitl_override_decision"]["override_decision_id"] == second["hitl_override_decision"]["override_decision_id"]


def test_multiple_override_artifacts_fail_closed(tmp_path: Path) -> None:
    preview = run_agent_golden_path(_config(tmp_path / "preview", force_review_required=True))
    p1 = _make_override(review_request=preview["hitl_review_request"], execution_record=preview["final_execution_record"])
    p2 = dict(p1)
    p2["override_decision_id"] = "hod-runtime-test-002"
    path1 = tmp_path / "override1.json"
    path2 = tmp_path / "override2.json"
    path1.write_text(json.dumps(p1, indent=2) + "\n", encoding="utf-8")
    path2.write_text(json.dumps(p2, indent=2) + "\n", encoding="utf-8")

    artifacts = run_agent_golden_path(
        _config(
            tmp_path / "run",
            force_review_required=True,
            require_override_decision=True,
            override_decision_paths=[path1, path2],
        )
    )

    action = artifacts["final_execution_record"]["actions_taken"][0]
    assert action["action_type"] == "hitl_override_enforcement_failed"
    assert action["reason"] == "override_ambiguous"
    assert artifacts["final_execution_record"]["execution_status"] == "blocked"
    assert "enforcement" not in artifacts
