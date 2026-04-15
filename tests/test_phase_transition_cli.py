from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from spectrum_systems.contracts import load_example


def test_phase_transition_cli(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    registry_path = tmp_path / "registry.json"
    checkpoint_path.write_text(json.dumps(load_example("phase_checkpoint_record")), encoding="utf-8")
    registry_path.write_text(json.dumps(load_example("phase_registry")), encoding="utf-8")
    cmd = [sys.executable, "scripts/run_phase_transition.py", "--checkpoint", str(checkpoint_path), "--registry", str(registry_path)]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["artifact_type"] == "phase_transition_policy_result"
