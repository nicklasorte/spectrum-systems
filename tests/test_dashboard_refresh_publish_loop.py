from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "dashboard_refresh_publish_loop.py"
GENERATOR = REPO_ROOT / "scripts" / "generate_repo_dashboard_snapshot.py"
PUBLIC = REPO_ROOT / "dashboard" / "public"
SNAPSHOT = REPO_ROOT / "artifacts" / "dashboard" / "repo_snapshot.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_repo_snapshot_timestamp_updates_on_each_generation_run() -> None:
    first = subprocess.run(
        ["python3", str(GENERATOR), "--output", str(SNAPSHOT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    first_payload = _read(SNAPSHOT)
    first_ts = first_payload["generated_at"]

    second = subprocess.run(
        ["python3", str(GENERATOR), "--output", str(SNAPSHOT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    second_payload = _read(SNAPSHOT)
    second_ts = second_payload["generated_at"]

    assert second_ts > first_ts
    assert second_payload["freshness_timestamp_utc"] == second_ts


def test_manual_refresh_emits_trace_linked_artifacts() -> None:
    completed = subprocess.run(
        ["python3", str(SCRIPT), "--mode", "manual", "--now", "2026-04-12T12:00:00Z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    refresh = _read(PUBLIC / "refresh_run_record.json")
    freshness = _read(PUBLIC / "dashboard_freshness_status.json")
    publication = _read(PUBLIC / "publication_attempt_record.json")

    assert refresh["artifact_type"] == "refresh_run_record"
    assert publication["artifact_type"] == "publication_attempt_record"
    assert refresh["trace_id"] == freshness["trace_id"] == publication["trace_id"]
    assert publication["decision"] == "allow"
    assert publication["trigger_mode"] == "manual"


def test_refresh_failure_injection_blocks_publication() -> None:
    completed = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--mode",
            "test",
            "--now",
            "2026-04-12T12:05:00Z",
            "--inject-failure",
            "malformed_manifest",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2


def test_malformed_snapshot_timestamp_fails_closed() -> None:
    completed = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--mode",
            "test",
            "--now",
            "2026-04-12T12:15:00Z",
            "--inject-failure",
            "malformed_timestamp",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0


def test_scheduled_and_manual_modes_share_contract_path() -> None:
    for mode, now in (("scheduled", "2026-04-12T12:10:00Z"), ("manual", "2026-04-12T12:10:01Z")):
        completed = subprocess.run(
            ["python3", str(SCRIPT), "--mode", mode, "--now", now],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        publication = _read(PUBLIC / "publication_attempt_record.json")
        refresh = _read(PUBLIC / "refresh_run_record.json")
        assert publication["trigger_mode"] == mode
        assert refresh["trigger_mode"] == mode
        assert publication["decision"] == "allow"
