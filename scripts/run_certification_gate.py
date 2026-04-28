#!/usr/bin/env python3
"""Canonical Certification Gate runner (TST-03/TST-14)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ARTIFACTS = [
    "outputs/contract_preflight/contract_preflight_result_artifact.json",
    "outputs/governance_gate/governance_gate_result.json",
    "outputs/runtime_test_gate/runtime_test_gate_result.json",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run certification gate")
    parser.add_argument("--output-dir", default="outputs/certification_gate")
    parser.add_argument("--mode", choices=["pr", "deep"], default="pr")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = [p for p in REQUIRED_ARTIFACTS if not (REPO_ROOT / p).is_file()]
    cmd = [sys.executable, "scripts/run_done_certification.py"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)

    status = "allow" if proc.returncode == 0 and not missing else "block"
    result = {
        "artifact_type": "certification_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "certification_gate",
        "status": status,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_certification_gate.py"},
        "provenance": {"mode": args.mode},
        "inputs": {"required_artifacts": REQUIRED_ARTIFACTS},
        "outputs": {"missing_required_artifacts": missing, "stdout_preview": proc.stdout[-500:], "stderr_preview": proc.stderr[-500:]},
        "executed_commands": [" ".join(cmd)],
        "selected_tests": [],
        "reason_codes": ["CERTIFICATION_PASS" if status == "allow" else "CERTIFICATION_BLOCK"],
        "failure_summary": {
            "gate_name": "certification_gate",
            "failure_class": "none" if status == "allow" else "certification_failure",
            "root_cause": "none" if status == "allow" else ("missing required artifacts" if missing else "done certification failed"),
            "blocking_reason": "none" if status == "allow" else (", ".join(missing) if missing else f"exit_code={proc.returncode}"),
            "next_action": "proceed" if status == "allow" else "generate missing artifacts and rerun",
            "affected_files": missing,
            "failed_command": "" if status == "allow" else " ".join(cmd),
            "artifact_refs": REQUIRED_ARTIFACTS,
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "certification_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "artifact": str(out)}, indent=2))
    return 0 if status == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
