"""Tests for deterministic, read-only prompt queue observability snapshots."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    generate_queue_snapshot,
    validate_observability_snapshot,
    validate_queue_invariants,
)


def _queue_state() -> dict:
    state = load_example("prompt_queue_state")
    state["work_items"] = [
        {
            **state["work_items"][0],
            "work_item_id": "wi-001",
            "status": "queued",
            "retry_count": 0,
            "retry_budget": 2,
        },
        {
            **state["work_items"][0],
            "work_item_id": "wi-002",
            "status": "executing",
            "retry_count": 1,
            "retry_budget": 3,
            "run_id": "run-100",
            "previous_status": "runnable",
        },
        {
            **state["work_items"][0],
            "work_item_id": "wi-003",
            "status": "complete",
            "retry_count": 2,
            "retry_budget": 2,
        },
        {
            **state["work_items"][0],
            "work_item_id": "wi-004",
            "status": "executed_failure",
            "retry_count": 1,
            "retry_budget": 1,
        },
        {
            **state["work_items"][0],
            "work_item_id": "wi-005",
            "status": "blocked",
            "retry_count": 0,
            "retry_budget": 1,
        },
    ]
    state["active_work_item_id"] = "wi-002"
    state["updated_at"] = "2026-03-22T00:00:00Z"
    return state


def test_snapshot_determinism():
    queue_state = _queue_state()
    first = generate_queue_snapshot(queue_state)
    second = generate_queue_snapshot(copy.deepcopy(queue_state))
    assert first == second
    assert first["queue_health_state"] in {"stable", "degraded", "unstable"}
    assert set(first["health_metrics"]) == {
        "queue_id",
        "current_step_index",
        "total_steps",
        "queue_status",
        "last_transition_action",
        "blocked_count",
        "retry_count",
        "remediation_count",
        "ambiguous_signal_count",
        "recovery_count",
        "completion_progress",
    }


def test_invariant_detection():
    queue_state = _queue_state()
    queue_state["work_items"][1]["run_id"] = "run-dup"
    queue_state["work_items"][2]["run_id"] = "run-dup"
    queue_state["work_items"][3]["retry_count"] = 5
    queue_state["work_items"][3]["retry_budget"] = 2
    queue_state["work_items"][4]["is_running"] = True
    queue_state["work_items"][0].pop("status")
    queue_state["work_items"][1]["previous_status"] = "queued"

    violations = validate_queue_invariants(queue_state)

    assert any(v.startswith("duplicate_run_id:run-dup") for v in violations)
    assert any(v.startswith("retry_count_exceeds_budget:wi-004") for v in violations)
    assert any(v.startswith("blocked_status_with_running_flag:wi-005") for v in violations)
    assert any(v.startswith("missing_required_fields:wi-001:status") for v in violations)
    assert any(v.startswith("invalid_state_transition:wi-002:queued->executing") for v in violations)


def test_no_mutation_of_queue():
    queue_state = _queue_state()
    before = copy.deepcopy(queue_state)

    _ = validate_queue_invariants(queue_state)
    _ = generate_queue_snapshot(queue_state)

    assert queue_state == before


def test_schema_validation(tmp_path: Path):
    queue_path = tmp_path / "queue.json"
    output_path = tmp_path / "snapshot.json"
    queue_path.write_text(json.dumps(_queue_state(), indent=2), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_prompt_queue_observability.py"),
            "--queue-path",
            str(queue_path),
            "--output-path",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    snapshot = json.loads(output_path.read_text(encoding="utf-8"))
    validate_observability_snapshot(snapshot)
    assert snapshot["snapshot_id"].startswith("pqo-")
    assert snapshot["queue_health_state"] in {"stable", "degraded", "unstable"}


def test_healthy_queue_classifies_stable():
    queue_state = _queue_state()
    queue_state["work_items"][4]["status"] = "queued"
    queue_state["queue_status"] = "running"

    snapshot = generate_queue_snapshot(queue_state)

    assert snapshot["health_metrics"]["blocked_count"] == 0
    assert snapshot["queue_health_state"] == "stable"


def test_blocked_queue_classifies_unstable():
    queue_state = _queue_state()
    snapshot = generate_queue_snapshot(queue_state)
    assert snapshot["health_metrics"]["blocked_count"] == 1
    assert snapshot["queue_health_state"] == "unstable"


def test_ambiguous_signals_classify_degraded():
    queue_state = _queue_state()
    queue_state["work_items"][4]["status"] = "queued"
    queue_state["active_work_item_id"] = None
    queue_state["queue_status"] = "running"

    snapshot = generate_queue_snapshot(queue_state)

    assert snapshot["health_metrics"]["ambiguous_signal_count"] == 1
    assert snapshot["queue_health_state"] == "degraded"


def test_malformed_artifact_input_fails_closed(tmp_path: Path):
    queue_path = tmp_path / "queue.json"
    output_path = tmp_path / "snapshot.json"
    malformed = _queue_state()
    malformed.pop("queue_id")
    queue_path.write_text(json.dumps(malformed, indent=2), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_prompt_queue_observability.py"),
            "--queue-path",
            str(queue_path),
            "--output-path",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "ERROR:" in completed.stderr
    assert not output_path.exists()


def test_missing_queue_lineage_fails_closed():
    queue_state = _queue_state()
    for item in queue_state["work_items"]:
        item.pop("run_id", None)
    queue_state["step_results"] = []
    with_value_error = False
    try:
        generate_queue_snapshot(queue_state)
    except ValueError as exc:
        with_value_error = True
        assert "missing queue state lineage" in str(exc)
    assert with_value_error is True
