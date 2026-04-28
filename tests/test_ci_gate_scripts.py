from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def test_test_selection_gate_emits_artifact() -> None:
    proc = _run("scripts/run_test_selection_gate.py", "--base-ref", "HEAD", "--head-ref", "HEAD", "--output-dir", "outputs/test_selection_gate_test")
    assert proc.returncode == 0
    artifact = REPO_ROOT / "outputs/test_selection_gate_test/test_selection_gate_result.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "test_selection_gate_result"


def test_runtime_test_gate_blocks_on_missing_selection_artifact() -> None:
    proc = _run("scripts/run_runtime_test_gate.py", "--selection-artifact", "outputs/does-not-exist.json", "--output-dir", "outputs/runtime_test_gate_test")
    assert proc.returncode != 0
    artifact = REPO_ROOT / "outputs/runtime_test_gate_test/runtime_test_gate_result.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["status"] == "block"


def test_pr_gate_help() -> None:
    proc = _run("scripts/run_pr_gate.py", "--help")
    assert proc.returncode == 0
    assert "Run PR canonical gates" in proc.stdout
