"""Tests for scripts/refresh_dashboard.sh publication hardening."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RQ_SCRIPT = REPO_ROOT / "scripts" / "run_rq_master_36_01.py"
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "refresh_dashboard.sh"
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"
RUNTIME_ARTIFACT = REPO_ROOT / "artifacts" / "rq_master_36_01" / "next_action_recommendation_record.json"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=check)


def test_refresh_publishes_audit_and_freshness_state() -> None:
    _run([sys.executable, str(RQ_SCRIPT)])
    _run(["bash", str(REFRESH_SCRIPT)])

    audit = json.loads((PUBLIC_ROOT / "dashboard_publication_sync_audit.json").read_text(encoding="utf-8"))
    freshness = json.loads((PUBLIC_ROOT / "dashboard_freshness_status.json").read_text(encoding="utf-8"))

    assert audit["publication_state"] == "live"
    assert isinstance(audit.get("records"), list)
    assert any(row.get("artifact") == "next_action_recommendation_record.json" for row in audit["records"])

    assert freshness["publication_state"] == "live"
    assert freshness["status"] in {"fresh", "stale"}
    assert freshness.get("snapshot_last_refreshed_time")


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
