"""Tests for scripts/refresh_dashboard.sh publication hardening."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RQ_SCRIPT = REPO_ROOT / "scripts" / "run_rq_master_36_01.py"
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "refresh_dashboard.sh"
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"
RUNTIME_ARTIFACT = REPO_ROOT / "artifacts" / "rq_master_36_01" / "next_action_recommendation_record.json"
TRIGGER_PATH = REPO_ROOT / "artifacts" / "rq_master_36_01" / "dashboard_refresh_trigger_manifest.json"
INVOKE_PATH = REPO_ROOT / "artifacts" / "rq_master_36_01" / "post_run_refresh_invocation_record.json"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=check)


def test_refresh_publishes_audit_and_freshness_state() -> None:
    _run([sys.executable, str(RQ_SCRIPT)])

    audit = json.loads((PUBLIC_ROOT / "dashboard_publication_sync_audit.json").read_text(encoding="utf-8"))
    freshness = json.loads((PUBLIC_ROOT / "dashboard_freshness_status.json").read_text(encoding="utf-8"))
    manifest = json.loads((PUBLIC_ROOT / "dashboard_publication_manifest.json").read_text(encoding="utf-8"))
    trigger = json.loads(TRIGGER_PATH.read_text(encoding="utf-8"))
    invoke = json.loads(INVOKE_PATH.read_text(encoding="utf-8"))

    assert audit["publication_state"] == "live"
    assert isinstance(audit.get("records"), list)
    assert any(row.get("artifact") == "next_action_recommendation_record.json" for row in audit["records"])

    assert freshness["publication_state"] == "live"
    assert freshness["status"] in {"fresh", "stale"}
    assert freshness.get("snapshot_last_refreshed_time")

    assert manifest["publication_mode"] == "atomic"
    assert trigger["refresh_required"] is True
    assert invoke["refresh_invoked"] is True
    assert invoke["refresh_returncode"] == 0


def test_refresh_fails_closed_when_required_source_missing() -> None:
    _run([sys.executable, str(RQ_SCRIPT)])
    backup = RUNTIME_ARTIFACT.with_suffix(".json.bak")
    shutil.copy2(RUNTIME_ARTIFACT, backup)
    RUNTIME_ARTIFACT.unlink()

    try:
        result = _run(["bash", str(REFRESH_SCRIPT)], check=False)
        assert result.returncode != 0
        assert "required governed publication sources missing" in result.stderr
    finally:
        shutil.move(backup, RUNTIME_ARTIFACT)


def test_failed_run_does_not_auto_refresh() -> None:
    if TRIGGER_PATH.exists():
        TRIGGER_PATH.unlink()
    if INVOKE_PATH.exists():
        INVOKE_PATH.unlink()

    result = _run([sys.executable, str(RQ_SCRIPT), "--fail-after-artifacts"], check=False)
    assert result.returncode != 0
    assert not TRIGGER_PATH.exists()
    assert not INVOKE_PATH.exists()


def test_refresh_uses_repo_snapshot_generated_at_for_freshness_contract() -> None:
    _run(["bash", str(REFRESH_SCRIPT)])
    first_snapshot = json.loads((PUBLIC_ROOT / "repo_snapshot.json").read_text(encoding="utf-8"))
    first_meta = json.loads((PUBLIC_ROOT / "repo_snapshot_meta.json").read_text(encoding="utf-8"))
    first_freshness = json.loads((PUBLIC_ROOT / "dashboard_freshness_status.json").read_text(encoding="utf-8"))

    assert first_snapshot["generated_at"] == first_meta["last_refreshed_time"]
    assert first_snapshot["generated_at"] == first_freshness["snapshot_last_refreshed_time"]

    time.sleep(1.1)
    _run(["bash", str(REFRESH_SCRIPT)])
    second_snapshot = json.loads((PUBLIC_ROOT / "repo_snapshot.json").read_text(encoding="utf-8"))
    second_meta = json.loads((PUBLIC_ROOT / "repo_snapshot_meta.json").read_text(encoding="utf-8"))
    second_freshness = json.loads((PUBLIC_ROOT / "dashboard_freshness_status.json").read_text(encoding="utf-8"))

    assert second_snapshot["generated_at"] == second_meta["last_refreshed_time"]
    assert second_snapshot["generated_at"] == second_freshness["snapshot_last_refreshed_time"]
    assert second_snapshot["generated_at"] != first_snapshot["generated_at"]
