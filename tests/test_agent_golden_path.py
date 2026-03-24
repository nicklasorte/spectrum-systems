from __future__ import annotations

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


def test_happy_path_end_to_end(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path))

    assert "failure_artifact" not in artifacts
    assert artifacts["agent_execution_trace"]["execution_status"] == "completed"
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

    assert artifacts["control_decision"]["system_response"] in {"block", "freeze"}
    assert artifacts["final_execution_record"]["execution_status"] == "blocked"


def test_deterministic_repeated_runs(tmp_path: Path) -> None:
    first = run_agent_golden_path(_config(tmp_path / "run1"))
    second = run_agent_golden_path(_config(tmp_path / "run2"))

    assert _normalized(first) == _normalized(second)


def test_artifact_completeness(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path))
    expected = {
        "context_bundle",
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
