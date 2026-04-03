from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.prompt_queue.queue_state_machine import (
    QueueLoopError,
    build_queue_resume_checkpoint,
    replay_queue_from_checkpoint,
    resume_queue_from_checkpoint,
)

TRACE_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _base_manifest(queue_id: str = "queue-test") -> dict:
    return {
        "queue_id": queue_id,
        "created_at": "2026-03-28T00:00:00Z",
        "version": "1.0.0",
        "steps": [
            {"step_id": "step-001", "step_type": "review", "input_refs": ["x"], "expected_outputs": ["y"], "metadata": {}},
            {"step_id": "step-002", "step_type": "repair", "input_refs": ["x"], "expected_outputs": ["y"], "metadata": {}},
            {"step_id": "step-003", "step_type": "execution", "input_refs": ["x"], "expected_outputs": ["y"], "metadata": {}},
        ],
        "execution_policy": {"allow_warn": False, "stop_on_block": True, "trace_id": TRACE_ID},
    }


def _base_state(result_ref: str, queue_id: str = "queue-test") -> dict:
    return {
        "queue_id": queue_id,
        "queue_status": "running",
        "work_items": [
            {
                "work_item_id": "wi-001",
                "parent_work_item_id": None,
                "prompt_id": "prompt-001",
                "title": "Queue replay test",
                "status": "queued",
                "priority": "high",
                "risk_level": "medium",
                "repo": "spectrum-systems",
                "branch": "feature/test",
                "scope_paths": ["spectrum_systems/modules/prompt_queue"],
                "review_provider_primary": "codex",
                "review_provider_actual": None,
                "review_attempt_count": 0,
                "review_fallback_used": False,
                "review_fallback_reason": None,
                "findings_artifact_path": None,
                "created_at": "2026-03-28T00:00:00Z",
                "updated_at": "2026-03-28T00:00:00Z",
                "repair_prompt_artifact_path": None,
                "gating_decision_artifact_path": None,
                "spawned_from_repair_prompt_artifact_path": None,
                "spawned_from_findings_artifact_path": None,
                "spawned_from_review_artifact_path": None,
                "generation_count": 0,
                "repair_loop_generation": 0,
                "child_work_item_ids": [],
                "loop_control_decision_artifact_path": None,
                "execution_result_artifact_path": None,
                "post_execution_decision_artifact_path": None,
                "next_step_action_artifact_path": None,
                "review_trigger_artifact_path": None,
                "review_invocation_result_artifact_path": None,
                "review_parsing_handoff_artifact_path": None,
                "findings_reentry_artifact_path": None,
                "spawned_from_execution_result_artifact_path": None,
                "spawned_from_post_execution_decision_artifact_path": None,
                "spawned_from_loop_control_decision_artifact_path": None,
                "loop_continuation_artifact_path": None,
                "blocked_recovery_decision_artifact_path": None,
                "retry_count": 0,
                "retry_budget": 2,
                "retry_decision_artifact_path": None,
            }
        ],
        "active_work_item_id": "wi-001",
        "created_at": "2026-03-28T00:00:00Z",
        "updated_at": "2026-03-28T00:05:00Z",
        "current_step_index": 1,
        "total_steps": 3,
        "step_results": [
            {
                "step_id": "step-001",
                "step_index": 0,
                "status": "completed",
                "result_ref": result_ref,
                "updated_at": "2026-03-28T00:05:00Z",
            }
        ],
        "last_updated": "2026-03-28T00:05:00Z",
    }


def _transition(queue_id: str = "queue-test", trace_id: str = TRACE_ID) -> dict:
    return {
        "transition_decision_id": "transition-001",
        "step_id": "step-001",
        "queue_id": queue_id,
        "trace_linkage": trace_id,
        "source_decision_ref": "step-decision-001",
        "transition_action": "continue",
        "transition_status": "allowed",
        "reason_codes": ["allow_clean_findings_continue"],
        "blocking_reasons": [],
        "derived_from_artifacts": ["exec-001"],
        "timestamp": "2026-03-28T00:05:00Z",
    }


def test_valid_checkpoint_creation_and_deterministic_ids(tmp_path: Path) -> None:
    transition_path = _write(tmp_path / "transition.json", _transition())
    queue_state = _base_state(result_ref=transition_path)

    checkpoint_a = build_queue_resume_checkpoint(
        queue_state,
        {
            "manifest_ref": str(tmp_path / "manifest.json"),
            "queue_state_ref": str(tmp_path / "queue_state.json"),
            "transition_decision_ref": transition_path,
            "trace_id": TRACE_ID,
            "timestamp": "2026-03-28T00:05:00Z",
        },
    )
    checkpoint_b = build_queue_resume_checkpoint(
        queue_state,
        {
            "manifest_ref": str(tmp_path / "manifest.json"),
            "queue_state_ref": str(tmp_path / "queue_state.json"),
            "transition_decision_ref": transition_path,
            "trace_id": TRACE_ID,
            "timestamp": "2026-03-28T00:05:00Z",
        },
    )

    assert checkpoint_a["checkpoint_id"] == checkpoint_b["checkpoint_id"]
    assert checkpoint_a["last_completed_step_index"] == 0


def test_resume_from_checkpoint_continues_correctly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transition_path = _write(tmp_path / "transition.json", _transition())
    manifest_path = _write(tmp_path / "manifest.json", _base_manifest())
    state_path = _write(tmp_path / "state.json", _base_state(result_ref=transition_path))

    checkpoint = build_queue_resume_checkpoint(
        _base_state(result_ref=transition_path),
        {
            "manifest_ref": manifest_path,
            "queue_state_ref": state_path,
            "transition_decision_ref": transition_path,
            "trace_id": TRACE_ID,
            "timestamp": "2026-03-28T00:05:00Z",
        },
    )

    def _fake_run_queue_once(queue_state: dict, manifest: dict) -> dict:
        out = dict(queue_state)
        out["current_step_index"] = 2
        out["step_results"] = [*queue_state["step_results"], {"step_id": "step-002", "step_index": 1, "status": "completed", "result_ref": "transition-002", "updated_at": "2026-03-28T00:06:00Z"}]
        return out

    monkeypatch.setattr("spectrum_systems.modules.prompt_queue.queue_state_machine.run_queue_once", _fake_run_queue_once)

    resumed = resume_queue_from_checkpoint(checkpoint)
    assert resumed["current_step_index"] == 2


def test_resume_with_missing_artifact_fails(tmp_path: Path) -> None:
    transition_path = _write(tmp_path / "transition.json", _transition())
    manifest_path = _write(tmp_path / "manifest.json", _base_manifest())
    state_path = _write(tmp_path / "state.json", _base_state(result_ref=transition_path))
    checkpoint = build_queue_resume_checkpoint(
        _base_state(result_ref=transition_path),
        {
            "manifest_ref": manifest_path,
            "queue_state_ref": state_path,
            "transition_decision_ref": transition_path,
            "trace_id": TRACE_ID,
            "timestamp": "2026-03-28T00:05:00Z",
        },
    )
    Path(state_path).unlink()
    with pytest.raises(QueueLoopError, match="missing or invalid artifact reference"):
        resume_queue_from_checkpoint(checkpoint)


def test_replay_parity_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transition_path = _write(tmp_path / "transition.json", _transition())
    manifest_path = _write(tmp_path / "manifest.json", _base_manifest())
    state_path = _write(tmp_path / "state.json", _base_state(result_ref=transition_path))

    checkpoint = build_queue_resume_checkpoint(
        _base_state(result_ref=transition_path),
        {
            "manifest_ref": manifest_path,
            "queue_state_ref": state_path,
            "transition_decision_ref": transition_path,
            "trace_id": TRACE_ID,
            "timestamp": "2026-03-28T00:05:00Z",
        },
    )

    def _deterministic_run(queue_state: dict, manifest: dict) -> dict:
        out = dict(queue_state)
        out["queue_status"] = "running"
        out["current_step_index"] = 2
        out["step_results"] = [*queue_state["step_results"], {"step_id": "step-002", "step_index": 1, "status": "completed", "result_ref": "decision-002", "updated_at": "2026-03-28T00:06:00Z"}]
        return out

    monkeypatch.setattr("spectrum_systems.modules.prompt_queue.queue_state_machine.run_queue_once", _deterministic_run)

    replay_record = replay_queue_from_checkpoint(checkpoint)
    assert replay_record["parity_status"] == "match"
    assert replay_record["mismatch_summary"] is None
    assert replay_record["replay_result_summary"]["termination_reason_match"] is True
    assert replay_record["replay_result_summary"]["decision_sequence_match"] is True
    assert replay_record["replay_result_summary"]["final_outcome_match"] is True


def test_replay_detects_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transition_path = _write(tmp_path / "transition.json", _transition())
    manifest_path = _write(tmp_path / "manifest.json", _base_manifest())
    state_path = _write(tmp_path / "state.json", _base_state(result_ref=transition_path))

    checkpoint = build_queue_resume_checkpoint(
        _base_state(result_ref=transition_path),
        {
            "manifest_ref": manifest_path,
            "queue_state_ref": state_path,
            "transition_decision_ref": transition_path,
            "trace_id": TRACE_ID,
            "timestamp": "2026-03-28T00:05:00Z",
        },
    )

    calls = {"n": 0}

    def _nondeterministic_run(queue_state: dict, manifest: dict) -> dict:
        calls["n"] += 1
        suffix = "A" if calls["n"] == 1 else "B"
        out = dict(queue_state)
        out["current_step_index"] = 2
        out["step_results"] = [*queue_state["step_results"], {"step_id": "step-002", "step_index": 1, "status": "completed", "result_ref": f"decision-{suffix}", "updated_at": "2026-03-28T00:06:00Z"}]
        return out

    monkeypatch.setattr("spectrum_systems.modules.prompt_queue.queue_state_machine.run_queue_once", _nondeterministic_run)

    replay_record = replay_queue_from_checkpoint(checkpoint)
    assert replay_record["parity_status"] == "mismatch"
    assert replay_record["mismatch_summary"]
    assert replay_record["replay_result_summary"]["decision_match"] is False
