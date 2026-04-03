from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.prompt_queue.queue_audit_bundle import (
    QueueAuditBundleError,
    build_queue_audit_bundle,
)


TRACE_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
QUEUE_ID = "queue-audit-001"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _manifest() -> dict:
    return {
        "queue_id": QUEUE_ID,
        "created_at": "2026-03-28T00:00:00Z",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": "step-001",
                "step_type": "execution",
                "input_refs": ["prompt_queue_work_item:wi-001"],
                "expected_outputs": ["prompt_queue_execution_result"],
                "metadata": {"slice": "QUEUE-11"},
            }
        ],
        "execution_policy": {"stop_on_block": True, "allow_warn": False, "trace_id": TRACE_ID},
    }


def _final_state() -> dict:
    return {
        "queue_id": QUEUE_ID,
        "queue_status": "completed",
        "work_items": [
            {
                "work_item_id": "wi-001",
                "parent_work_item_id": None,
                "prompt_id": "prompt-001",
                "title": "Queue audit bundle",
                "status": "complete",
                "priority": "high",
                "risk_level": "medium",
                "repo": "spectrum-systems",
                "branch": "feature/pqx-queue-11",
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
        "updated_at": "2026-03-28T00:06:00Z",
        "current_step_index": 1,
        "total_steps": 1,
        "step_results": [
            {
                "step_id": "step-001",
                "step_index": 0,
                "status": "completed",
                "result_ref": "artifacts/prompt_queue/transitions/step-001.transition_decision.json",
                "updated_at": "2026-03-28T00:06:00Z",
            }
        ],
        "last_updated": "2026-03-28T00:06:00Z",
    }


def _execution_result() -> dict:
    return {
        "execution_result_artifact_id": "execres-wi-001-attempt-1",
        "step_id": "step-001",
        "queue_id": QUEUE_ID,
        "trace_linkage": TRACE_ID,
        "execution_type": "queue_step",
        "work_item_id": "wi-001",
        "parent_work_item_id": None,
        "repair_prompt_artifact_path": "artifacts/prompt_queue/repair_prompts/wi-001.repair_prompt.json",
        "gating_decision_artifact_path": "artifacts/prompt_queue/gating/wi-001.execution_gating_decision.json",
        "spawned_from_findings_artifact_path": "artifacts/prompt_queue/findings/wi-001.findings.json",
        "spawned_from_review_artifact_path": "artifacts/prompt_queue/reviews/wi-001.review.md",
        "execution_mode": "simulated",
        "execution_status": "success",
        "started_at": "2026-03-28T00:05:00Z",
        "completed_at": "2026-03-28T00:05:01Z",
        "output_reference": "artifacts/prompt_queue/simulated_outputs/wi-001.output.json",
        "produced_artifact_refs": ["artifacts/prompt_queue/simulated_outputs/wi-001.output.json"],
        "error_summary": None,
        "generated_at": "2026-03-28T00:05:01Z",
        "generator_version": "prompt-queue-execution-mvp-1",
        "source_queue_state_path": "artifacts/prompt_queue/queue_state.json",
        "execution_attempt_id": "wi-001-attempt-1",
    }


def _step_decision() -> dict:
    return {
        "decision_id": "step-decision-step-001-20260328T000510Z",
        "step_id": "step-001",
        "queue_id": QUEUE_ID,
        "trace_linkage": TRACE_ID,
        "decision": "allow",
        "reason_codes": ["clean_findings"],
        "blocking_reasons": [],
        "derived_from_artifacts": ["execres-wi-001-attempt-1"],
        "timestamp": "2026-03-28T00:05:10Z",
        "generator_version": "prompt_queue_step_decision.v1",
    }


def _transition_decision(step_decision_ref: str) -> dict:
    return {
        "transition_decision_id": "transition-decision-step-001-20260328T000520Z",
        "step_id": "step-001",
        "queue_id": QUEUE_ID,
        "trace_linkage": TRACE_ID,
        "source_decision_ref": step_decision_ref,
        "transition_action": "continue",
        "transition_status": "allowed",
        "reason_codes": ["allow_clean_findings_continue"],
        "blocking_reasons": [],
        "derived_from_artifacts": ["execres-wi-001-attempt-1"],
        "timestamp": "2026-03-28T00:05:20Z",
    }


def _observability() -> dict:
    snapshot = load_example("prompt_queue_observability_snapshot")
    snapshot["snapshot_id"] = "pqo-audit-001"
    snapshot["timestamp"] = "2026-03-28T00:06:00Z"
    snapshot["trace_linkage"] = {"linkage_type": "result_ref", "linkage_id": "artifacts/prompt_queue/transitions/step-001.transition_decision.json"}
    snapshot["health_metrics"]["queue_id"] = QUEUE_ID
    snapshot["health_metrics"]["current_step_index"] = 1
    snapshot["health_metrics"]["total_steps"] = 1
    snapshot["health_metrics"]["queue_status"] = "completed"
    snapshot["health_metrics"]["completion_progress"] = 1.0
    return snapshot


def _checkpoint(manifest_ref: str, state_ref: str, transition_ref: str) -> dict:
    return {
        "checkpoint_id": "checkpoint-" + ("a" * 64),
        "queue_id": QUEUE_ID,
        "manifest_ref": manifest_ref,
        "queue_state_ref": state_ref,
        "last_completed_step_index": 0,
        "last_transition_decision_ref": transition_ref,
        "trace_id": TRACE_ID,
        "created_at": "2026-03-28T00:06:00Z",
    }


def _replay_record(checkpoint_ref: str, manifest_ref: str, state_ref: str) -> dict:
    return {
        "replay_id": "queue-replay-" + ("b" * 64),
        "queue_id": QUEUE_ID,
        "checkpoint_ref": checkpoint_ref,
        "input_refs": [checkpoint_ref, manifest_ref, state_ref],
        "replay_result_summary": {
            "replayed_step_id": "step-001",
            "decision_match": True,
            "state_match": True,
            "transition_match": True,
            "termination_reason_match": True,
            "decision_sequence_match": True,
            "final_outcome_match": True,
        },
        "parity_status": "match",
        "mismatch_summary": None,
        "trace_id": TRACE_ID,
        "timestamp": "2026-03-28T00:06:30Z",
    }


def _certification(manifest_ref: str, state_ref: str, observability_ref: str, replay_checkpoint_ref: str) -> dict:
    return {
        "certification_id": "c" * 64,
        "queue_id": QUEUE_ID,
        "manifest_ref": manifest_ref,
        "final_queue_state_ref": state_ref,
        "replay_checkpoint_refs": [replay_checkpoint_ref],
        "observability_ref": observability_ref,
        "certification_status": "passed",
        "system_response": "allow",
        "check_results": {
            "queue_completion": {"passed": True, "details": []},
            "state_integrity": {"passed": True, "details": []},
            "replay_integrity": {"passed": True, "details": []},
            "observability_integrity": {"passed": True, "details": []},
            "artifact_completeness": {"passed": True, "details": []},
        },
        "blocking_reasons": [],
        "trace_id": TRACE_ID,
        "timestamp": "2026-03-28T00:06:45Z",
    }


def _input_refs(tmp_path: Path) -> dict[str, str | list[str]]:
    manifest_ref = _write(tmp_path / "manifest.json", _manifest())
    state_ref = _write(tmp_path / "state.json", _final_state())
    execution_ref = _write(tmp_path / "execution.json", _execution_result())
    step_decision_ref = _write(tmp_path / "step_decision.json", _step_decision())
    transition_ref = _write(tmp_path / "transition.json", _transition_decision(step_decision_ref))
    observability_ref = _write(tmp_path / "observability.json", _observability())
    checkpoint_ref = _write(tmp_path / "checkpoint.json", _checkpoint(manifest_ref, state_ref, transition_ref))
    replay_ref = _write(tmp_path / "replay.json", _replay_record(checkpoint_ref, manifest_ref, state_ref))
    certification_ref = _write(
        tmp_path / "certification.json",
        _certification(manifest_ref, state_ref, observability_ref, checkpoint_ref),
    )
    return {
        "manifest_ref": manifest_ref,
        "final_queue_state_ref": state_ref,
        "execution_result_refs": [execution_ref],
        "step_decision_refs": [step_decision_ref],
        "transition_decision_refs": [transition_ref],
        "replay_refs": [checkpoint_ref, replay_ref],
        "observability_ref": observability_ref,
        "certification_ref": certification_ref,
    }


def test_complete_queue_run_builds_complete_audit_bundle(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    bundle = build_queue_audit_bundle(refs)
    assert bundle["lineage_status"] == "complete"
    assert bundle["completeness_status"] == "complete"
    validate_artifact(bundle, "prompt_queue_audit_bundle")


def test_missing_execution_artifact_marks_bundle_incomplete(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    refs["execution_result_refs"] = []
    with pytest.raises(QueueAuditBundleError, match="missing required input ref list: execution_result_refs"):
        build_queue_audit_bundle(refs)  # type: ignore[arg-type]


def test_missing_certification_ref_fails_fast(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    refs.pop("certification_ref")
    with pytest.raises(QueueAuditBundleError, match="missing required input ref: certification_ref"):
        build_queue_audit_bundle(refs)  # type: ignore[arg-type]


def test_disconnected_lineage_marks_bundle_incomplete(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    transition_path = Path(refs["transition_decision_refs"][0])  # type: ignore[index]
    transition = json.loads(transition_path.read_text(encoding="utf-8"))
    transition["trace_linkage"] = "trace-disconnected"
    transition_path.write_text(json.dumps(transition), encoding="utf-8")
    bundle = build_queue_audit_bundle(refs)
    assert bundle["lineage_status"] == "incomplete"
    assert bundle["completeness_status"] == "incomplete"


def test_deterministic_output(tmp_path: Path) -> None:
    refs = _input_refs(tmp_path)
    first = build_queue_audit_bundle(refs)
    second = build_queue_audit_bundle(refs)
    assert first == second


def test_schema_example_validates() -> None:
    validate_artifact(load_example("prompt_queue_audit_bundle"), "prompt_queue_audit_bundle")
