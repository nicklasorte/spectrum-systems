"""Tests for scripts/run_rq_master_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_rq_master_01.py"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "RQ-MASTER-01-artifact-trace.json"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "rq_master_01"

PHASE_CHECKPOINTS = [
    "phase-1_checkpoint.json",
    "phase-2_checkpoint.json",
    "phase-3_checkpoint.json",
    "phase-4_checkpoint.json",
    "phase-5_checkpoint.json",
]


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_phase_checkpoints_and_trace() -> None:
    _run_script()
    assert TRACE_PATH.is_file()

    for checkpoint in PHASE_CHECKPOINTS:
        assert (ARTIFACT_ROOT / checkpoint).is_file()


def test_phase_delivery_contract_and_final_gate_present() -> None:
    _run_script()
    phase3 = _load_json(ARTIFACT_ROOT / "phase-3_checkpoint.json")
    assert phase3["checkpoint_status"] == "pass"
    assert "delivery_contract" in phase3
    assert "certification_readiness_impact" in phase3["delivery_contract"]

    trace = _load_json(TRACE_PATH)
    assert trace["phase_sequence"] == ["PHASE-1", "PHASE-2", "PHASE-3", "PHASE-4", "PHASE-5"]
    assert trace["final_gate"]["gate_name"] == "bounded_expansion_gate"
    assert trace["final_gate"]["result"] == "pass"
