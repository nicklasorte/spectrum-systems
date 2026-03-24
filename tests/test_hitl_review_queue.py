from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.agent_golden_path import GoldenPathConfig, run_agent_golden_path


def _config(tmp_path: Path, **overrides: object) -> GoldenPathConfig:
    base = {
        "task_type": "meeting_minutes",
        "input_payload": {"transcript": "AG-03 deterministic runtime transcript"},
        "source_artifacts": [{"artifact_id": "artifact-001", "kind": "source"}],
        "context_config": {},
        "output_dir": tmp_path,
    }
    base.update(overrides)
    return GoldenPathConfig(**base)


def test_hitl_review_request_example_validates() -> None:
    validate_artifact(load_example("hitl_review_request"), "hitl_review_request")


def test_control_triggered_review_request_schema_validates(tmp_path: Path) -> None:
    artifacts = run_agent_golden_path(_config(tmp_path, force_eval_status="fail", force_control_block=True))

    review_request = artifacts["hitl_review_request"]
    validate_artifact(review_request, "hitl_review_request")
    assert review_request["trigger_stage"] == "control"
    assert review_request["trigger_reason"] == "control_non_allow_response"
    assert review_request["status"] == "pending_review"


def test_review_request_id_is_deterministic(tmp_path: Path) -> None:
    first = run_agent_golden_path(_config(tmp_path / "run1", force_review_required=True))
    second = run_agent_golden_path(_config(tmp_path / "run2", force_review_required=True))

    assert first["hitl_review_request"]["id"] == second["hitl_review_request"]["id"]
    assert first["hitl_review_request"]["source_artifact_ids"] == second["hitl_review_request"]["source_artifact_ids"]
