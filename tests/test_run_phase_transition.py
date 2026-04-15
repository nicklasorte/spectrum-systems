from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_phase_transition_cli_allows_progress(tmp_path: Path) -> None:
    checkpoint = {
        "artifact_type": "phase_checkpoint_record",
        "schema_version": "1.0.0",
        "trace_id": "trace-cli",
        "phase_id": "PHASE_A",
        "phase_label": "Core hardening",
        "status": "COMPLETE",
        "blocking_reason_codes": [],
        "required_fix_refs": [],
        "required_review_refs": [],
        "completed_step_refs": ["WPG-25"],
        "next_phase": "PHASE_B",
        "resume_ready": True,
        "policy_version": "1.0.0",
        "replay_signature_refs": ["sig:abc"]
    }
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps(checkpoint), encoding="utf-8")
    cmd = [sys.executable, "scripts/run_phase_transition.py", "--checkpoint", str(path)]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "ALLOW"
