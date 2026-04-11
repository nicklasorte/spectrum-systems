"""Tests for scripts/validate_dashboard_public_artifacts.py."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RQ_SCRIPT = REPO_ROOT / "scripts" / "run_rq_master_36_01.py"
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "refresh_dashboard.sh"
VALIDATOR = REPO_ROOT / "scripts" / "validate_dashboard_public_artifacts.py"
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"
META_PATH = PUBLIC_ROOT / "repo_snapshot_meta.json"
FRESHNESS_PATH = PUBLIC_ROOT / "dashboard_freshness_status.json"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_validator_passes_for_fresh_public_artifacts() -> None:
    _run([sys.executable, str(RQ_SCRIPT)])
    _run(["bash", str(REFRESH_SCRIPT)])
    _run([sys.executable, str(VALIDATOR)])


def test_validator_fails_on_stale_snapshot_meta() -> None:
    _run([sys.executable, str(RQ_SCRIPT)])
    _run(["bash", str(REFRESH_SCRIPT)])

    original_meta = _read_json(META_PATH)
    original_freshness = _read_json(FRESHNESS_PATH)

    stale = dict(original_meta)
    stale["last_refreshed_time"] = (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale["data_source_state"] = "live"
    _write_json(META_PATH, stale)

    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert result.returncode != 0
    assert "stale" in result.stderr.lower() or "freshness" in result.stderr.lower()

    _write_json(META_PATH, original_meta)
    _write_json(FRESHNESS_PATH, original_freshness)


def test_validator_fails_on_fallback_live_ambiguity() -> None:
    _run([sys.executable, str(RQ_SCRIPT)])
    _run(["bash", str(REFRESH_SCRIPT)])

    original_freshness = _read_json(FRESHNESS_PATH)
    ambiguous = dict(original_freshness)
    ambiguous["publication_state"] = "fallback"
    _write_json(FRESHNESS_PATH, ambiguous)

    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert result.returncode != 0
    assert "ambiguity" in result.stderr.lower()

    _write_json(FRESHNESS_PATH, original_freshness)
