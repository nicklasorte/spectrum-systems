from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_golden_path import GoldenPathConfig, run_agent_golden_path
from spectrum_systems.modules.runtime.evaluation_auto_generation import (
    generate_failure_eval_case,
    register_failure_eval_case,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _config(tmp_path: Path, **overrides: object) -> GoldenPathConfig:
    base = {
        "task_type": "meeting_minutes",
        "input_payload": {"transcript": "AG-02 failure coverage transcript"},
        "source_artifacts": [{"artifact_id": "artifact-001", "kind": "source"}],
        "context_config": {},
        "output_dir": tmp_path,
    }
    base.update(overrides)
    return GoldenPathConfig(**base)


def test_failure_artifact_schema_and_completeness(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_eval_execution=True))
    failure = artifacts["failure_artifact"]

    validate_artifact(failure, "agent_failure_record")
    assert failure["failure_stage"] == "eval"
    assert failure["failure_type"] == "execution_error"
    assert failure["root_artifact_ids"]["context_bundle_id"]
    assert failure["root_artifact_ids"]["agent_run_id"]
    assert failure["root_artifact_ids"]["eval_case_id"]
    assert failure["root_artifact_ids"]["eval_run_id"] is None
    assert (tmp_path / "failure_artifact.json").exists()


def test_failure_artifact_is_deterministic_for_identical_failure_inputs(tmp_path: Path) -> None:
    first = run_agent_golden_path(_config(tmp_path / "r1", fail_control_decision=True))["failure_artifact"]
    second = run_agent_golden_path(_config(tmp_path / "r2", fail_control_decision=True))["failure_artifact"]

    assert first == second


def test_all_failure_stages_route_to_agent_failure_record(tmp_path: Path) -> None:
    scenarios = [
        ("context", {"fail_context_assembly": True}),
        ("agent", {"fail_agent_execution": True}),
        ("normalization", {"emit_invalid_structured_output": True}),
        ("eval", {"fail_eval_execution": True}),
        ("control", {"fail_control_decision": True}),
        ("enforcement", {"fail_enforcement": True}),
    ]
    for stage, overrides in scenarios:
        artifacts = run_agent_golden_path(_config(tmp_path / stage, **overrides))
        assert "failure_artifact" in artifacts
        failure = artifacts["failure_artifact"]
        validate_artifact(failure, "agent_failure_record")
        assert failure["failure_stage"] == stage


def test_cli_failure_returns_non_zero_and_emits_failure_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_agent_golden_path.py",
            "--fail-agent-execution",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["status"] == "failed"
    assert payload["failure_stage"] == "agent"
    assert (output_dir / "failure_artifact.json").exists()


def test_failure_generates_eval_case_and_registers_policy_binding(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, fail_eval_execution=True))
    failure = artifacts["failure_artifact"]
    failure_eval_case = generate_failure_eval_case(
        source_artifact=failure,
        source_run_id=failure["run_id"],
        stage=failure["failure_stage"],
        runtime_environment="agent_golden_path",
        execution_result={
            "continuation_allowed": False,
            "publication_blocked": True,
            "decision_blocked": True,
            "human_review_required": False,
            "escalation_triggered": True,
        },
    )
    registry: dict[str, dict] = {}
    binding = register_failure_eval_case(
        failure_eval_case=failure_eval_case,
        eval_registry=registry,
        policy_id="failure-binding-policy-v1",
        trigger_condition="on_agent_failure_record",
    )
    assert failure_eval_case["eval_case_id"]
    assert failure_eval_case["failure_class"]
    assert failure_eval_case["trace_id"] == failure["trace_id"]
    assert registry[failure_eval_case["eval_case_id"]]["failure_id"] == failure["id"]
    assert binding["policy_id"].startswith("failure-binding-policy-v1::")
