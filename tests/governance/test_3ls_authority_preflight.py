"""Tests for the 3LS combined authority preflight script.

Verifies that run_3ls_authority_preflight.py runs cleanly against the current
repo state and that its output artifact is well-formed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = REPO_ROOT / "outputs" / "authority_shape_preflight" / "3ls_authority_preflight_result.json"


@pytest.fixture(scope="module")
def preflight_result() -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_3ls_authority_preflight.py"),
            "--suggest-only",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert RESULT_PATH.is_file(), (
        f"3ls preflight result not written; stderr: {proc.stderr}"
    )
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def test_3ls_preflight_passes(preflight_result: dict) -> None:
    assert preflight_result["status"] == "pass", (
        f"3LS authority preflight failed:\n{json.dumps(preflight_result, indent=2)}"
    )


def test_3ls_preflight_zero_violations(preflight_result: dict) -> None:
    assert preflight_result["total_violation_count"] == 0


def test_3ls_preflight_includes_shape_check(preflight_result: dict) -> None:
    assert "authority_shape_preflight" in preflight_result["checks"]


def test_3ls_preflight_shape_check_passed(preflight_result: dict) -> None:
    shape = preflight_result["checks"]["authority_shape_preflight"]
    assert shape["status"] == "pass"
    assert shape["violation_count"] == 0


def test_3ls_preflight_shape_check_scanned_files(preflight_result: dict) -> None:
    shape = preflight_result["checks"]["authority_shape_preflight"]
    assert shape["scanned_file_count"] > 0


def test_3ls_preflight_result_artifact_written() -> None:
    assert RESULT_PATH.is_file()
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert "status" in payload
    assert "total_violation_count" in payload
    assert "checks" in payload
