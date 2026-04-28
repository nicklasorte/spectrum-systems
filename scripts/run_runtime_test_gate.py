#!/usr/bin/env python3
"""Runtime test gate runner for fast PR and deep modes."""

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

    selected_tests: list[str] = []
    selection_status = "block"
    if selection_path.is_file():
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        selected_tests = [str(t) for t in selection.get("selected_tests", [])]
        selection_status = str(selection.get("status", "block"))

    commands: list[str] = []
    out_preview = ""
    err_preview = ""
    test_exit = 0

    if selection_status != "allow":
        status = "block"
        reason_codes = ["SELECTION_GATE_BLOCK"]
        test_exit = 2
    elif not selected_tests:
        status = "allow"
        reason_codes = ["NO_RUNTIME_TARGETS_FOR_DIFF"]
    else:
        cmd = [sys.executable, "-m", "pytest", *selected_tests]
        commands.append(" ".join(cmd))
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        test_exit = proc.returncode
        out_preview = proc.stdout[-1500:]
        err_preview = proc.stderr[-1500:]
        status = "allow" if test_exit == 0 else "block"
        reason_codes = ["PYTEST_PASS" if status == "allow" else "PYTEST_FAIL"]

    result = {
        "artifact_type": "runtime_test_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "runtime_test_gate",
        "status": status,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_runtime_test_gate.py"},
        "provenance": {"selection_artifact": args.selection_artifact},
        "inputs": {"selected_tests_count": len(selected_tests), "selection_status": selection_status},
        "outputs": {"stdout_preview": out_preview, "stderr_preview": err_preview},
        "executed_commands": commands,
        "selected_tests": selected_tests,
        "reason_codes": reason_codes,
        "failure_summary": {
            "gate_name": "runtime_test_gate",
            "failure_class": "none" if status == "allow" else "runtime_test_failure",
            "root_cause": "none" if status == "allow" else "selection gate blocked or pytest failed",
            "blocking_reason": "none" if status == "allow" else f"exit_code={test_exit}",
            "next_action": "proceed" if status == "allow" else "fix selected test surface or runtime failures",
            "affected_files": selected_tests,
            "failed_command": "" if status == "allow" else (commands[-1] if commands else "selection gate blocked"),
            "artifact_refs": [args.selection_artifact],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "runtime_test_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "artifact": str(out)}, indent=2))
    return 0 if status in {"allow", "warn"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
