from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.agent_golden_path import GoldenPathConfig, run_agent_golden_path


def _config(tmp_path: Path, **overrides: object) -> GoldenPathConfig:
    base = {
        "task_type": "meeting_minutes",
        "input_payload": {"transcript": "AG-01 deterministic runtime transcript"},
        "source_artifacts": [{"artifact_id": "artifact-001", "kind": "source"}],
        "context_config": {},
        "output_dir": tmp_path,
    }
    base.update(overrides)
    return GoldenPathConfig(**base)


def _normalized(artifacts: dict) -> dict:
    normalized = {}
    for key, value in artifacts.items():
        if not isinstance(value, dict):
            normalized[key] = value
            continue
        clone = dict(value)
        for ts in ("created_at", "timestamp", "started_at", "completed_at"):
            clone.pop(ts, None)
        if "metadata" in clone and isinstance(clone["metadata"], dict):
            clone["metadata"] = dict(clone["metadata"])
            clone["metadata"].pop("created_at", None)
        if "actions_taken" in clone and isinstance(clone["actions_taken"], list):
            sanitized = []
            for action in clone["actions_taken"]:
                if isinstance(action, dict):
                    action_copy = dict(action)
                    action_copy.pop("timestamp", None)
                    sanitized.append(action_copy)
            clone["actions_taken"] = sanitized
        normalized[key] = clone
    return normalized


def _override_payload(review_request: dict, execution_record: dict, **overrides: object) -> dict:
    payload = {
        "artifact_type": "hitl_override_decision",
        "schema_version": "1.0.0",
        "override_decision_id": "hod-test-001",
        "created_at": "2026-01-05T14:22:31Z",
        "trace_id": review_request["trace_id"],
        "review_request_id": review_request["id"],
        "related_execution_record_id": execution_record["artifact_id"],
        "decision_status": "allow_once",
        "decision_reason": "Approved for deterministic one-time continuation.",
        "decided_by": {"actor_id": "reviewer-test", "role": "control_authority_reviewer"},
        "decision_scope": "ag_runtime_review_boundary",
        "allowed_next_action": "resume_once",
        "trace_refs": {"primary": review_request["trace_id"], "related": [review_request["trace_id"]]},
        "related_artifact_refs": [
            f"hitl_review_request:{review_request['id']}",
            f"final_execution_record:{execution_record['artifact_id']}",
        ],
    }
    payload.update(overrides)
    return payload


def test_happy_path_end_to_end(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path))

    assert "failure_artifact" not in artifacts
    assert artifacts["agent_execution_trace"]["execution_status"] == "completed"
    assert artifacts["routing_decision"]["artifact_type"] == "routing_decision"
    assert artifacts["routing_decision"]["selected_prompt_id"] == "ag.runtime.default"
    assert artifacts["routing_decision"]["resolved_prompt_version"] == "v1.0.0"
    assert artifacts["routing_decision"]["selected_prompt_alias"] == "prod"
    assert artifacts["agent_execution_trace"]["prompt_resolution"]["prompt_id"] == "ag.runtime.default"
    assert artifacts["agent_execution_trace"]["prompt_resolution"]["prompt_version"] == "v1.0.0"
    assert artifacts["agent_execution_trace"]["prompt_resolution"]["requested_alias"] == "prod"
    assert artifacts["agent_execution_trace"]["routing_decision"]["routing_decision_id"] == artifacts["routing_decision"]["routing_decision_id"]
    assert artifacts["agent_execution_trace"]["context_source_summary"]["prompt_injection"]["detection_status"] == "clean"
    assert artifacts["agent_execution_trace"]["context_source_summary"]["prompt_injection"]["enforcement_action"] == "allow_as_data"
    assert len(artifacts["agent_execution_trace"]["model_invocations"]) == 1
    model_invocation = artifacts["agent_execution_trace"]["model_invocations"][0]
    assert model_invocation["requested_model_id"] == "openai:gpt-4o-mini"
    assert model_invocation["provider_name"] == "openai"
    assert model_invocation["provider_model_name"] == "gpt-4o-mini"
    assert model_invocation["structured_generation_mode"] == "unstructured"
    assert model_invocation["structured_target_schema_ref"] is None
    assert model_invocation["structured_enforcement_path"] == "none"
    assert model_invocation["structured_output_status"] == "not_requested"
    assert artifacts["structured_output"]["artifact_type"] == "eval_case"
    assert artifacts["eval_result"]["result_status"] == "pass"
    assert artifacts["control_decision"]["system_response"] == "allow"
    assert artifacts["final_execution_record"]["execution_status"] == "success"


def test_context_failure_stops_pipeline(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_context_assembly=True))

    assert artifacts["failure_artifact"]["failure_stage"] == "context"
    assert "context_bundle" not in artifacts
    assert "agent_execution_trace" not in artifacts


def test_agent_execution_failure_stops_pipeline(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_agent_execution=True))

    assert artifacts["failure_artifact"]["failure_stage"] == "agent"
    assert "eval_result" not in artifacts
    assert "control_decision" not in artifacts


def test_invalid_output_schema_stops_pipeline(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, emit_invalid_structured_output=True))

    assert artifacts["failure_artifact"]["failure_stage"] == "normalization"
    assert "structured_output" not in artifacts
    assert "eval_result" not in artifacts


def test_eval_failure_stops_pipeline(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_eval_execution=True))

    assert artifacts["failure_artifact"]["failure_stage"] == "eval"
    assert "eval_summary" not in artifacts
    assert "control_decision" not in artifacts


def test_control_failure_stops_pipeline(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_control_decision=True))

    assert artifacts["failure_artifact"]["failure_stage"] == "control"
    assert "control_decision" not in artifacts
    assert "enforcement" not in artifacts


def test_enforcement_failure_stops_pipeline(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_enforcement=True))

    assert artifacts["failure_artifact"]["failure_stage"] == "enforcement"
    assert "enforcement" not in artifacts
    assert "final_execution_record" not in artifacts


def test_control_block_path(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, force_eval_status="fail", force_control_block=True))

    assert artifacts["control_decision"]["system_response"] in {"block", "freeze", "warn"}
    assert artifacts["hitl_review_request"]["trigger_reason"] == "control_non_allow_response"
    assert artifacts["final_execution_record"]["execution_status"] == "escalated"
    assert "enforcement" not in artifacts


def test_force_review_required_stops_before_control(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, force_review_required=True))

    assert artifacts["hitl_review_request"]["trigger_reason"] == "forced_review_required"
    assert artifacts["hitl_review_request"]["status"] == "pending_review"
    assert artifacts["final_execution_record"]["execution_status"] == "escalated"
    assert "control_decision" not in artifacts
    assert "enforcement" not in artifacts


def test_indeterminate_review_path_emits_review_artifact(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, force_indeterminate_review=True))

    assert artifacts["hitl_review_request"]["trigger_stage"] == "eval"
    assert artifacts["hitl_review_request"]["trigger_reason"] == "indeterminate_outcome_routed_to_human"
    assert artifacts["final_execution_record"]["human_review_required"] is True
    assert "control_decision" not in artifacts




def test_unknown_route_key_fails_closed_without_default(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, route_key="unknown_route_key"))

    assert artifacts["failure_artifact"]["failure_stage"] == "agent"
    assert artifacts["failure_artifact"]["failure_type"] == "policy_error"
    assert "agent_execution_trace" not in artifacts


def test_context_bundle_runtime_linkage_present(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path))

    bundle = artifacts["context_bundle"]
    trace = artifacts["agent_execution_trace"]

    assert bundle["context_bundle_id"] == trace["context_bundle_id"]
    assert bundle["trace"]["trace_id"] == trace["trace_id"]
    assert bundle["trace"]["run_id"] == trace["agent_run_id"]


def test_routing_decision_trace_linkage_present(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path))

    routing = artifacts["routing_decision"]
    trace = artifacts["agent_execution_trace"]
    invocation = trace["model_invocations"][0]

    assert routing["trace"]["trace_id"] == trace["trace_id"]
    assert routing["trace"]["agent_run_id"] == trace["agent_run_id"]
    assert invocation["requested_model_id"] == routing["selected_model_id"]

def test_deterministic_repeated_runs(tmp_path: Path) -> None:
    first = run_agent_golden_path(_config(tmp_path / "run1"))
    second = run_agent_golden_path(_config(tmp_path / "run2"))

    assert _normalized(first) == _normalized(second)


def test_artifact_completeness(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path))
    expected = {
        "context_bundle",
        "routing_decision",
        "agent_execution_trace",
        "structured_output",
        "eval_result",
        "eval_summary",
        "control_decision",
        "enforcement",
        "final_execution_record",
    }
    assert expected.issubset(artifacts.keys())
    for name in expected:
        assert (tmp_path / f"{name}.json").exists()


def test_review_required_writes_expected_artifacts(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, force_review_required=True))

    assert "failure_artifact" not in artifacts
    assert (tmp_path / "hitl_review_request.json").exists()
    assert (tmp_path / "final_execution_record.json").exists()
    assert not (tmp_path / "enforcement.json").exists()


def test_review_required_with_valid_override_resumes_once(tmp_path: Path) -> None:
    preview = run_agent_golden_path(_config(tmp_path / "preview", force_review_required=True))
    override_path = tmp_path / "override.json"
    override_path.write_text(
        json.dumps(_override_payload(preview["hitl_review_request"], preview["final_execution_record"]), indent=2) + "\n",
        encoding="utf-8",
    )

    artifacts = run_agent_golden_path(
        _config(
            tmp_path / "resume",
            force_review_required=True,
            override_decision_paths=[override_path],
            require_override_decision=True,
        )
    )

    assert "failure_artifact" not in artifacts
    assert artifacts["final_execution_record"]["execution_status"] == "success"
    assert artifacts["hitl_override_decision"]["decision_status"] == "allow_once"
    assert "enforcement" in artifacts
