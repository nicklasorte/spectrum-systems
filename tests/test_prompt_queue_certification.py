from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.prompt_queue.queue_certification import QueueCertificationError, run_queue_certification


TRACE_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _manifest(queue_id: str = "queue-cert-001") -> dict:
    return {
        "queue_id": queue_id,
        "created_at": "2026-03-28T00:00:00Z",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": "step-001",
                "step_type": "execution",
                "input_refs": ["prompt_queue_work_item:wi-001"],
                "expected_outputs": ["prompt_queue_execution_result"],
                "metadata": {},
            }
        ],
        "execution_policy": {"stop_on_block": True, "allow_warn": False, "trace_id": TRACE_ID},
    }


def _final_queue_state(queue_id: str = "queue-cert-001") -> dict:
    return {
        "queue_id": queue_id,
        "queue_status": "completed",
        "work_items": [
            {
                "work_item_id": "wi-001",
                "parent_work_item_id": None,
                "prompt_id": "prompt-001",
                "title": "Queue certification",
                "status": "complete",
                "priority": "high",
                "risk_level": "medium",
                "repo": "spectrum-systems",
                "branch": "feature/pqx-queue-10",
                "scope_paths": ["spectrum_systems/modules/prompt_queue"],
                "review_provider_primary": "codex",
                "review_provider_actual": None,
                "review_attempt_count": 0,
                "review_fallback_used": False,
                "review_fallback_reason": None,
                "findings_artifact_path": "artifacts/prompt_queue/findings/wi-001.findings.json",
                "created_at": "2026-03-28T00:00:00Z",
                "updated_at": "2026-03-28T00:05:00Z",
                "repair_prompt_artifact_path": "artifacts/prompt_queue/repair_prompts/wi-001.repair_prompt.json",
                "gating_decision_artifact_path": "artifacts/prompt_queue/gating/wi-001.execution_gating_decision.json",
                "spawned_from_repair_prompt_artifact_path": None,
                "spawned_from_findings_artifact_path": "artifacts/prompt_queue/findings/wi-001.findings.json",
                "spawned_from_review_artifact_path": "artifacts/prompt_queue/reviews/wi-001.review.md",
                "generation_count": 0,
                "repair_loop_generation": 0,
                "child_work_item_ids": [],
                "loop_control_decision_artifact_path": "artifacts/prompt_queue/loop_control/wi-001.loop_control_decision.json",
                "execution_result_artifact_path": "artifacts/prompt_queue/execution_results/wi-001.execution_result.json",
                "post_execution_decision_artifact_path": "artifacts/prompt_queue/post_execution_decisions/wi-001.post_execution_decision.json",
                "next_step_action_artifact_path": "artifacts/prompt_queue/next_step_actions/wi-001.next_step_action.json",
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
        "active_work_item_id": None,
        "created_at": "2026-03-28T00:00:00Z",
        "updated_at": "2026-03-28T00:05:00Z",
        "current_step_index": 1,
        "total_steps": 1,
        "step_results": [
            {
                "step_id": "step-001",
                "step_index": 0,
                "status": "completed",
                "result_ref": "artifacts/prompt_queue/transitions/step-001.transition_decision.json",
                "updated_at": "2026-03-28T00:05:00Z",
            }
        ],
        "last_updated": "2026-03-28T00:05:00Z",
    }


def _observability(queue_id: str = "queue-cert-001") -> dict:
    return {
        "snapshot_id": "pqo-cert-001",
        "timestamp": "2026-03-28T00:05:00Z",
        "total_items": 1,
        "items_by_status": {"queued": 0, "running": 0, "completed": 1, "failed": 0, "blocked": 0},
        "retry_counts_summary": {"total_retry_count": 0, "max_retry_count": 0, "items_with_retries": 0},
        "blocked_items_count": 0,
        "exhausted_retry_count": 0,
        "active_run_ids": [],
        "invariant_violations": [],
        "trace_linkage": {"linkage_type": "result_ref", "linkage_id": "artifacts/prompt_queue/transitions/step-001.transition_decision.json"},
        "queue_health_state": "stable",
        "health_reason_codes": [],
        "health_metrics": {
            "queue_id": queue_id,
            "current_step_index": 1,
            "total_steps": 1,
            "queue_status": "completed",
            "last_transition_action": "continue",
            "blocked_count": 0,
            "retry_count": 0,
            "remediation_count": 0,
            "ambiguous_signal_count": 0,
            "recovery_count": 0,
            "completion_progress": 1.0,
        },
    }


def _checkpoint(queue_id: str = "queue-cert-001") -> dict:
    return {
        "checkpoint_id": "checkpoint-" + "a" * 64,
        "queue_id": queue_id,
        "manifest_ref": "manifest.json",
        "queue_state_ref": "state.json",
        "last_completed_step_index": 0,
        "last_transition_decision_ref": "artifacts/prompt_queue/transitions/step-001.transition_decision.json",
        "trace_id": TRACE_ID,
        "created_at": "2026-03-28T00:05:00Z",
    }


def _replay_record(queue_id: str = "queue-cert-001") -> dict:
    return {
        "replay_id": "queue-replay-" + "b" * 64,
        "queue_id": queue_id,
        "checkpoint_ref": "checkpoint.json",
        "input_refs": ["checkpoint.json", "manifest.json", "state.json"],
        "replay_result_summary": {
            "replayed_step_id": "step-001",
            "decision_match": True,
            "state_match": True,
            "transition_match": True,
        },
        "parity_status": "match",
        "mismatch_summary": None,
        "trace_id": TRACE_ID,
        "timestamp": "2026-03-28T00:06:00Z",
    }


def _input_refs(tmp_path: Path) -> dict[str, str | list[str]]:
    manifest_path = _write(tmp_path / "manifest.json", _manifest())
    state_path = _write(tmp_path / "state.json", _final_queue_state())
    observability_path = _write(tmp_path / "observability.json", _observability())

    checkpoint = _checkpoint()
    checkpoint["manifest_ref"] = manifest_path
    checkpoint["queue_state_ref"] = state_path
    checkpoint_path = _write(tmp_path / "checkpoint.json", checkpoint)

    replay = _replay_record()
    replay["checkpoint_ref"] = checkpoint_path
    replay["input_refs"] = [checkpoint_path, manifest_path, state_path]
    replay_path = _write(tmp_path / "replay_record.json", replay)

    return {
        "manifest_ref": manifest_path,
        "final_queue_state_ref": state_path,
        "observability_ref": observability_path,
        "replay_checkpoint_refs": [checkpoint_path],
        "replay_record_ref": replay_path,
    }


def test_valid_complete_queue_run_passes(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    artifact = run_queue_certification(refs)
    assert artifact["certification_status"] == "passed"
    assert artifact["system_response"] == "allow"
    assert artifact["blocking_reasons"] == []


def test_incomplete_queue_state_fails(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    state_path = Path(refs["final_queue_state_ref"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["queue_status"] = "running"
    state["active_work_item_id"] = "wi-001"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    artifact = run_queue_certification(refs)
    assert artifact["certification_status"] == "failed"
    assert "queue_not_completed" in artifact["blocking_reasons"]


def test_missing_artifact_fails(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    Path(refs["observability_ref"]).unlink()

    artifact = run_queue_certification(refs)
    assert artifact["certification_status"] == "failed"
    assert any(reason.startswith("missing_or_invalid_observability") for reason in artifact["blocking_reasons"])


def test_replay_resume_inconsistency_fails(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    replay_path = Path(refs["replay_record_ref"])
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    replay["parity_status"] = "mismatch"
    replay["mismatch_summary"] = "transition mismatch"
    replay_path.write_text(json.dumps(replay), encoding="utf-8")

    artifact = run_queue_certification(refs)
    assert artifact["certification_status"] == "failed"
    assert "replay_parity_mismatch" in artifact["blocking_reasons"]


def test_observability_mismatch_fails(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    obs_path = Path(refs["observability_ref"])
    snapshot = json.loads(obs_path.read_text(encoding="utf-8"))
    snapshot["health_metrics"]["queue_status"] = "running"
    obs_path.write_text(json.dumps(snapshot), encoding="utf-8")

    artifact = run_queue_certification(refs)
    assert artifact["certification_status"] == "failed"
    assert "observability_queue_status_mismatch" in artifact["blocking_reasons"]


def test_deterministic_output(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    first = run_queue_certification(refs)
    second = run_queue_certification(refs)
    assert first == second


def test_missing_final_queue_state_ref_fails_fast() -> None:
    with pytest.raises(QueueCertificationError, match="missing required input ref: final_queue_state_ref"):
        run_queue_certification({"manifest_ref": "a", "observability_ref": "b"})


def test_malformed_input_refs_fail_fast() -> None:
    with pytest.raises(QueueCertificationError, match="input_refs must be an object"):
        run_queue_certification([])  # type: ignore[arg-type]
