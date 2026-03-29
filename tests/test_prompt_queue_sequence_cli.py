from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_SEQUENCE = REPO_ROOT / "scripts" / "run_prompt_queue_sequence.py"


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _slice_requests() -> list[dict]:
    return [
        {"slice_id": "PQX-QUEUE-01", "trace_id": "trace-01"},
        {"slice_id": "PQX-QUEUE-02", "trace_id": "trace-02"},
    ]


def test_cli_success_returns_zero_and_writes_state(tmp_path: Path) -> None:
    state_path = tmp_path / "sequence_state.json"
    slices_path = tmp_path / "slices.json"
    _write_json(slices_path, _slice_requests())

    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_SEQUENCE),
            "--state-path",
            str(state_path),
            "--slices-path",
            str(slices_path),
            "--queue-run-id",
            "queue-run-001",
            "--run-id",
            "run-001",
            "--trace-id",
            "trace-batch-001",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "completed"
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["completed_slice_ids"] == ["PQX-QUEUE-01", "PQX-QUEUE-02"]


def test_cli_failure_returns_nonzero_for_continuity_error(tmp_path: Path) -> None:
    state_path = tmp_path / "sequence_state.json"
    slices_path = tmp_path / "slices.json"
    _write_json(slices_path, [{"slice_id": "PQX-QUEUE-01", "trace_id": ""}])

    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_SEQUENCE),
            "--state-path",
            str(state_path),
            "--slices-path",
            str(slices_path),
            "--queue-run-id",
            "queue-run-001",
            "--run-id",
            "run-001",
            "--trace-id",
            "trace-batch-001",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "trace_id" in proc.stderr
