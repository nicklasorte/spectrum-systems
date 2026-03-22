from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_eval_registry_snapshot.py"


def test_cli_valid_build_path(tmp_path: Path) -> None:
    policy = REPO_ROOT / "contracts" / "examples" / "eval_admission_policy.json"
    dataset = REPO_ROOT / "contracts" / "examples" / "eval_dataset.json"
    output = tmp_path / "snapshot.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--policy",
            str(policy),
            "--datasets",
            str(dataset),
            "--snapshot-id",
            "snapshot-cli-1",
            "--trace-id",
            "trace-cli-1",
            "--run-id",
            "run-cli-1",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "eval_registry_snapshot"
    assert payload["active_policy_id"] == "policy-bbc-core"


def test_cli_invalid_policy_path_fail_closed(tmp_path: Path) -> None:
    dataset = REPO_ROOT / "contracts" / "examples" / "eval_dataset.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--policy",
            str(tmp_path / "missing-policy.json"),
            "--datasets",
            str(dataset),
            "--snapshot-id",
            "snapshot-cli-2",
            "--trace-id",
            "trace-cli-2",
            "--run-id",
            "run-cli-2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0


def test_cli_rejects_dataset_policy_mismatch(tmp_path: Path) -> None:
    policy = REPO_ROOT / "contracts" / "examples" / "eval_admission_policy.json"
    dataset = REPO_ROOT / "contracts" / "examples" / "eval_dataset.json"
    mismatched_dataset = tmp_path / "mismatched_dataset.json"

    payload = json.loads(dataset.read_text(encoding="utf-8"))
    payload["admission_policy_id"] = "policy-other"
    mismatched_dataset.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--policy",
            str(policy),
            "--datasets",
            str(mismatched_dataset),
            "--snapshot-id",
            "snapshot-cli-3",
            "--trace-id",
            "trace-cli-3",
            "--run-id",
            "run-cli-3",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "active_policy_id mismatch" in proc.stderr
