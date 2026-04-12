from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_rax_operational_gate_cli_passes_and_emits_artifact(tmp_path: Path) -> None:
    output = tmp_path / "gate.json"
    output_dir = tmp_path / "rax-ops"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_rax_operational_gate.py"),
        "--output",
        str(output),
        "--output-dir",
        str(output_dir),
    ]
    proc = subprocess.run(cmd, check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "rax_operational_gate_record"
    assert payload["decision"] == "promote_candidate"
    for name in (
        "rax_trend_report.json",
        "rax_trust_posture_snapshot.json",
        "rax_improvement_recommendation_record.json",
        "rax_judgment_record.json",
        "rax_promotion_hard_gate_record.json",
    ):
        assert (output_dir / name).is_file()


def test_run_rax_operational_gate_cli_fail_closed_on_freeze(tmp_path: Path) -> None:
    output = tmp_path / "gate-fail.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_rax_operational_gate.py"),
        "--output",
        str(output),
        "--fail-freeze",
    ]
    proc = subprocess.run(cmd, check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert "material_conflicts_unresolved" in payload["blocking_reasons"]
