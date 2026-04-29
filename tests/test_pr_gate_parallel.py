"""Tests for PR gate aggregation (fail-closed behavior)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_GATE_SCRIPT = REPO_ROOT / "scripts" / "run_pr_gate.py"
_REQUIRED_SHARDS = ["contract", "governance", "dashboard", "changed_scope"]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_selection(tmp: Path, shard: str, status: str = "selected", tests: list = None):
    d = tmp / shard
    d.mkdir(parents=True, exist_ok=True)
    sel = {
        "artifact_type": "pr_test_shard_selection",
        "schema_version": "1.0.0",
        "mode": "ci",
        "shard_name": shard,
        "base_ref": "abc",
        "head_ref": "def",
        "changed_paths": [],
        "governed_surfaces": [],
        "selected_test_files": tests or [],
        "coverage_ratio": 0.0,
        "fallback_used": False,
        "status": status,
        "reason_codes": [],
        "trace_refs": [],
        "authority_scope": "observation_only",
    }
    (d / f"{shard}_selection.json").write_text(json.dumps(sel))


def _write_result(tmp: Path, shard: str, status: str = "pass", failure_summary=None):
    d = tmp / shard
    d.mkdir(parents=True, exist_ok=True)
    res = {
        "artifact_type": "pr_test_shard_result",
        "schema_version": "1.0.0",
        "shard_name": shard,
        "status": status,
        "selected_tests": [],
        "commands_run": ["python -m pytest"],
        "duration_ms": 100,
        "failure_summary": failure_summary,
        "artifact_refs": [],
        "trace_refs": [],
        "authority_scope": "observation_only",
    }
    (d / f"{shard}_result.json").write_text(json.dumps(res))


def _run_gate(tmp: Path, output: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(_GATE_SCRIPT),
            "--shard-dir", str(tmp),
            "--output", str(output),
            "--required-shards", ",".join(_REQUIRED_SHARDS),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _setup_all_pass(tmp: Path):
    for shard in _REQUIRED_SHARDS:
        _write_selection(tmp, shard, status="selected", tests=["tests/test_something.py"])
        _write_result(tmp, shard, status="pass")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_shards_pass_produces_pass_gate(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 0, f"Expected exit 0, got {proc.returncode}\nstderr={proc.stderr}"
    result = json.loads(output.read_text())
    assert result["status"] == "pass"


def test_missing_shard_selection_artifact_blocks(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Remove the selection for one shard
    (tmp_path / "contract" / "contract_selection.json").unlink()
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    assert "missing_shard_selection_artifact" in reasons_str


def test_missing_shard_result_artifact_blocks(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Remove the result for one shard
    (tmp_path / "governance" / "governance_result.json").unlink()
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    assert "missing_shard_result_artifact" in reasons_str


def test_invalid_shard_selection_json_blocks(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Overwrite selection with invalid JSON
    (tmp_path / "dashboard" / "dashboard_selection.json").write_text("not json{{")
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    # Either missing or invalid artifact error is acceptable
    assert "missing_shard_selection_artifact" in reasons_str or "invalid_shard_selection_artifact" in reasons_str


def test_invalid_shard_result_json_blocks(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Overwrite result with invalid JSON
    (tmp_path / "changed_scope" / "changed_scope_result.json").write_text("{{bad}")
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    assert "missing_shard_result_artifact" in reasons_str or "invalid_shard_result_artifact" in reasons_str


def test_failed_shard_blocks_gate(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Overwrite contract result as failed
    _write_result(tmp_path, "contract", status="fail", failure_summary="Test assertion failed")
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    assert "shard_failed" in reasons_str


def test_blocked_shard_selection_blocks_gate(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Overwrite governance selection as blocked
    _write_selection(tmp_path, "governance", status="block")
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    assert "shard_selection_blocked" in reasons_str


def test_skipped_required_shard_blocks_without_empty_allowed(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Selection status "selected" but result status "skipped"
    _write_selection(tmp_path, "dashboard", status="selected", tests=["tests/test_dashboard.py"])
    _write_result(tmp_path, "dashboard", status="skipped")
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text())
    reasons_str = " ".join(result["blocking_reasons"])
    assert "skipped_required_shard" in reasons_str


def test_empty_allowed_selection_with_skipped_result_passes(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    # Selection is empty_allowed + result is skipped → should be OK
    _write_selection(tmp_path, "changed_scope", status="empty_allowed")
    _write_result(tmp_path, "changed_scope", status="skipped")
    proc = _run_gate(tmp_path, output)
    # All other shards pass; this one is ok_empty
    assert proc.returncode == 0
    result = json.loads(output.read_text())
    assert result["status"] == "pass"


def test_aggregator_does_not_recompute_selection(tmp_path):
    output = tmp_path / "gate_result.json"
    _setup_all_pass(tmp_path)
    proc = _run_gate(tmp_path, output)
    assert proc.returncode == 0
    result = json.loads(output.read_text())
    # The gate result aggregates shard results — it must NOT include selected_test_files
    assert "selected_test_files" not in result, (
        "Aggregator must not recompute or re-emit selected_test_files"
    )
