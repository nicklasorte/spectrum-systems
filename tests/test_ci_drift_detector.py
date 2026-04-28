from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_drift_detector_emits_result() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/run_ci_drift_detector.py", "--output", "outputs/ci_drift_detector/test_result.json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode in (0, 2)
    output = REPO_ROOT / "outputs/ci_drift_detector/test_result.json"
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "ci_drift_detector_result"
    assert payload["status"] in {"allow", "block"}
