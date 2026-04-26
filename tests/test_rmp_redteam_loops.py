from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_attestation_script_generates_required_artifacts() -> None:
    subprocess.run([sys.executable, "scripts/run_rmp_certification.py"], cwd=ROOT, check=True)

    drift = json.loads((ROOT / "artifacts/rmp_drift_report.json").read_text(encoding="utf-8"))
    delivery = json.loads((ROOT / "artifacts/rmp_01_delivery_report.json").read_text(encoding="utf-8"))

    assert drift["status"] == "pass"
    assert delivery["attestation"]["status"] == "pass"
    assert delivery["h01_readiness"]["ready"] is True
