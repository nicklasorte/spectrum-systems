#!/usr/bin/env python3
"""Canonical Runtime Test Gate runner (TST-03)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run runtime test gate")
    parser.add_argument("--selection-artifact", default="outputs/test_selection_gate/test_selection_gate_result.json")
    parser.add_argument("--output-dir", default="outputs/runtime_test_gate")
    args = parser.parse_args()

    selection_path = REPO_ROOT / args.selection_artifact
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not selection_path.is_file():
        selected_tests = []
        selection_status = "block"
    else:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        selected_tests = selection.get("selected_tests", [])
        selection_status = selection.get("status", "block")

    commands = []
    test_exit = 0
    out_preview = ""
    err_preview = ""
    if selection_status == "allow" and selected_tests:
        cmd = [sys.executable, "-m", "pytest", *selected_tests]
        commands.append(" ".join(cmd))
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        test_exit = proc.returncode
        out_preview = proc.stdout[-1500:]
        err_preview = proc.stderr[-1500:]
    else:
        test_exit = 2

    status = "allow" if test_exit == 0 else "block"
    result = {
        "artifact_type": "runtime_test_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "runtime_test_gate",
        "status": status,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_runtime_test_gate.py"},
        "provenance": {"selection_artifact": args.selection_artifact},
        "inputs": {"selected_tests_count": len(selected_tests)},
        "outputs": {"stdout_preview": out_preview, "stderr_preview": err_preview},
        "executed_commands": commands,
        "selected_tests": selected_tests,
        "reason_codes": ["PYTEST_PASS" if status == "allow" else "PYTEST_FAIL_OR_SELECTION_BLOCK"],
        "failure_summary": {
            "gate_name": "runtime_test_gate",
            "failure_class": "none" if status == "allow" else "runtime_test_failure",
            "root_cause": "none" if status == "allow" else "pytest failed or selection gate blocked",
            "blocking_reason": "none" if status == "allow" else f"exit_code={test_exit}",
            "next_action": "proceed" if status == "allow" else "fix failing tests or selection policy",
            "affected_files": selected_tests,
            "failed_command": "" if status == "allow" else (commands[-1] if commands else "selection blocked"),
            "artifact_refs": [args.selection_artifact],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "runtime_test_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "artifact": str(out)}, indent=2))
    return 0 if status == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
