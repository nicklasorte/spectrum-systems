#!/usr/bin/env python3
"""Canonical Contract Gate runner (TST-03)."""

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
    parser = argparse.ArgumentParser(description="Run canonical contract gate")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--output-dir", default="outputs/contract_gate")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    legacy_output_dir = REPO_ROOT / "outputs/contract_preflight"
    command = [
        sys.executable,
        "scripts/run_contract_preflight.py",
        "--base-ref",
        args.base_ref,
        "--head-ref",
        args.head_ref,
        "--output-dir",
        str(legacy_output_dir),
        "--execution-context",
        "pqx_governed",
    ]
    proc = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)

    status = "allow" if proc.returncode == 0 else "block"
    result = {
        "artifact_type": "contract_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "contract_gate",
        "status": status,
        "trace": {
            "produced_at": _utc_now(),
            "producer_script": "scripts/run_contract_gate.py",
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False).stdout.strip(),
        },
        "provenance": {"base_ref": args.base_ref, "head_ref": args.head_ref},
        "inputs": {"legacy_output_dir": str(legacy_output_dir)},
        "outputs": {
            "legacy_result_ref": "outputs/contract_preflight/contract_preflight_result_artifact.json",
            "stdout_preview": proc.stdout[-1000:],
            "stderr_preview": proc.stderr[-1000:],
        },
        "executed_commands": [" ".join(command)],
        "selected_tests": [],
        "reason_codes": ["CONTRACT_PREFLIGHT_PASS" if status == "allow" else "CONTRACT_PREFLIGHT_BLOCK"],
        "failure_summary": {
            "gate_name": "contract_gate",
            "failure_class": "none" if status == "allow" else "contract_preflight_failure",
            "root_cause": "none" if status == "allow" else "run_contract_preflight returned non-zero",
            "blocking_reason": "none" if status == "allow" else f"exit_code={proc.returncode}",
            "next_action": "proceed" if status == "allow" else "inspect outputs/contract_preflight artifacts",
            "affected_files": [],
            "failed_command": "" if status == "allow" else " ".join(command),
            "artifact_refs": ["outputs/contract_preflight/contract_preflight_result_artifact.json"],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out_path = output_dir / "contract_gate_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "artifact": str(out_path)}, indent=2))
    return 0 if status == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
