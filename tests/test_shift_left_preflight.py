from __future__ import annotations

import json
from pathlib import Path
import subprocess


def test_shift_left_entrypoint_coverage_audit_outputs_artifact(tmp_path: Path) -> None:
    proc = subprocess.run(
        ["python", "scripts/run_shift_left_entrypoint_coverage_audit.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode in {0, 1}
    artifact = Path("outputs/shift_left_hardening/entrypoint_coverage_audit.json")
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["required_front_door"] == "scripts/run_shift_left_preflight.py"


def test_shift_left_preflight_blocks_full_pytest_without_targeted_rerun(tmp_path: Path) -> None:
    output_path = tmp_path / "slh.json"
    remediation_path = tmp_path / "remediation.json"
    proc = subprocess.run(
        [
            "python",
            "scripts/run_shift_left_preflight.py",
            "--output",
            str(output_path),
            "--remediation-output",
            str(remediation_path),
            "--changed-file",
            "scripts/run_shift_left_hardening_superlayer.py",
            "--changed-file",
            "tests/test_shift_left_hardening_superlayer.py",
            "--",
            "pytest",
            "-q",
            "tests/test_shift_left_hardening_superlayer.py",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert "remediation_ref" in payload
    assert remediation_path.is_file()


def test_shift_left_workflow_coverage_audit_outputs_artifacts() -> None:
    proc = subprocess.run(
        ["python", "scripts/run_shift_left_workflow_coverage_audit.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode in {0, 1}
    coverage = Path("outputs/shift_left_hardening/workflow_coverage_audit.json")
    enforcement = Path("outputs/shift_left_hardening/workflow_front_door_enforcement.json")
    assert coverage.is_file()
    assert enforcement.is_file()
    payload = json.loads(coverage.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "con_shift_left_workflow_coverage_audit_result"
