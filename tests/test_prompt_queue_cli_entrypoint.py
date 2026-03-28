from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_QUEUE = REPO_ROOT / "scripts" / "run_prompt_queue.py"
RUN_QUEUE_EXECUTION = REPO_ROOT / "scripts" / "run_prompt_queue_execution.py"


def _base_manifest() -> dict:
    return {
        "queue_id": "queue-001",
        "created_at": "2026-03-28T00:00:00Z",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": "step-001",
                "step_type": "execution",
                "input_refs": ["prompt_queue_work_item:wi-001"],
                "expected_outputs": ["prompt_queue_execution_result"],
                "metadata": {"execution_mode": "simulated"},
            }
        ],
        "execution_policy": {
            "stop_on_block": True,
            "allow_warn": False,
            "trace_id": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    }


def _base_queue_state() -> dict:
    return {
        "queue_id": "queue-001",
        "queue_status": "running",
        "work_items": [
            {
                "work_item_id": "wi-001",
                "parent_work_item_id": None,
                "prompt_id": "prompt-gpq-001",
                "title": "Queue CLI entrypoint coverage",
                "status": "runnable",
                "priority": "high",
                "risk_level": "medium",
                "repo": "spectrum-systems",
                "branch": "feature/pqx-queue-09",
                "scope_paths": ["scripts"],
                "review_provider_primary": "codex",
                "review_provider_actual": None,
                "review_attempt_count": 0,
                "review_fallback_used": False,
                "review_fallback_reason": None,
                "created_at": "2026-03-28T00:00:00Z",
                "updated_at": "2026-03-28T00:00:00Z",
                "findings_artifact_path": None,
                "repair_prompt_artifact_path": "artifacts/prompt_queue/repair_prompts/wi-001.repair_prompt.json",
                "spawned_from_repair_prompt_artifact_path": None,
                "spawned_from_findings_artifact_path": "artifacts/prompt_queue/findings/wi-001.findings.json",
                "spawned_from_review_artifact_path": "docs/reviews/wi-001.md",
                "repair_loop_generation": 0,
                "child_work_item_ids": [],
                "gating_decision_artifact_path": "artifacts/prompt_queue/gating/wi-001.execution_gating_decision.json",
                "execution_result_artifact_path": None,
                "post_execution_decision_artifact_path": None,
                "next_step_action_artifact_path": None,
                "generation_count": 0,
                "loop_control_decision_artifact_path": None,
                "review_trigger_artifact_path": None,
                "spawned_from_execution_result_artifact_path": None,
                "spawned_from_post_execution_decision_artifact_path": None,
                "spawned_from_loop_control_decision_artifact_path": None,
                "review_invocation_result_artifact_path": None,
                "review_parsing_handoff_artifact_path": None,
                "findings_reentry_artifact_path": None,
                "loop_continuation_artifact_path": None,
                "blocked_recovery_decision_artifact_path": None,
                "retry_count": 0,
                "retry_budget": 2,
                "retry_decision_artifact_path": None,
            }
        ],
        "active_work_item_id": "wi-001",
        "created_at": "2026-03-28T00:00:00Z",
        "updated_at": "2026-03-28T00:00:00Z",
        "current_step_index": 0,
        "total_steps": 1,
        "step_results": [],
        "last_updated": "2026-03-28T00:00:00Z",
    }


def _write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_canonical_cli_runs_single_step_successfully(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queue_state_path = tmp_path / "queue_state.json"
    output_path = tmp_path / "updated_state.json"
    _write_json(manifest_path, _base_manifest())
    _write_json(queue_state_path, _base_queue_state())

    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_QUEUE),
            "--manifest-path",
            str(manifest_path),
            "--queue-state-path",
            str(queue_state_path),
            "--output-path",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["queue_status"] == "completed"
    assert payload["current_step_index"] == 1


def test_canonical_cli_fails_closed_for_blocked_queue_state(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queue_state_path = tmp_path / "queue_state.json"
    queue_state = _base_queue_state()
    queue_state["queue_status"] = "blocked"
    _write_json(manifest_path, _base_manifest())
    _write_json(queue_state_path, queue_state)

    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_QUEUE),
            "--manifest-path",
            str(manifest_path),
            "--queue-state-path",
            str(queue_state_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "next step cannot be determined" in proc.stderr


def test_canonical_cli_fails_closed_for_malformed_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queue_state_path = tmp_path / "queue_state.json"
    _write_json(manifest_path, ["not", "an", "object"])
    _write_json(queue_state_path, _base_queue_state())

    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_QUEUE),
            "--manifest-path",
            str(manifest_path),
            "--queue-state-path",
            str(queue_state_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "manifest artifact" in proc.stderr


def test_execution_cli_can_delegate_to_canonical_entrypoint(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queue_state_path = tmp_path / "queue_state.json"
    output_path = tmp_path / "delegated_output.json"
    _write_json(manifest_path, _base_manifest())
    _write_json(queue_state_path, _base_queue_state())

    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_QUEUE_EXECUTION),
            "--manifest-path",
            str(manifest_path),
            "--queue-state-path",
            str(queue_state_path),
            "--output-path",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["queue_status"] == "completed"


def test_no_duplicate_queue_loop_logic_across_queue_scripts() -> None:
    queue_scripts = [
        REPO_ROOT / "scripts" / "run_prompt_queue.py",
        REPO_ROOT / "scripts" / "run_prompt_queue_next_step.py",
        REPO_ROOT / "scripts" / "run_prompt_queue_execution.py",
        REPO_ROOT / "scripts" / "run_prompt_queue_resume.py",
        REPO_ROOT / "scripts" / "run_prompt_queue_replay.py",
        REPO_ROOT / "scripts" / "run_prompt_queue_observability.py",
    ]

    run_queue_once_occurrences = []
    for script_path in queue_scripts:
        contents = script_path.read_text(encoding="utf-8")
        if "run_queue_once" in contents:
            run_queue_once_occurrences.append(script_path.name)

    assert run_queue_once_occurrences == ["run_prompt_queue.py"]
