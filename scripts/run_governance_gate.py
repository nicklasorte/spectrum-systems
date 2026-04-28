#!/usr/bin/env python3
"""Canonical Governance Gate runner (TST-03)."""

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
    parser = argparse.ArgumentParser(description="Run governance gate")
    parser.add_argument("--output-dir", default="outputs/governance_gate")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        [sys.executable, "scripts/run_system_registry_guard.py"],
        [sys.executable, "scripts/run_required_check_alignment_audit.py", "--output-dir", "outputs/required_check_alignment_audit"],
    ]

    previews = []
    status = "allow"
    executed = []
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        executed.append(" ".join(cmd))
        previews.append({"cmd": " ".join(cmd), "exit_code": proc.returncode, "stdout": proc.stdout[-400:], "stderr": proc.stderr[-400:]})
        if proc.returncode != 0:
            status = "block"

    result = {
        "artifact_type": "governance_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "governance_gate",
        "status": status,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_governance_gate.py"},
        "provenance": {"governance_sources": ["docs/governance", "docs/architecture/system_registry.md"]},
        "inputs": {},
        "outputs": {"command_previews": previews},
        "executed_commands": executed,
        "selected_tests": [],
        "reason_codes": ["GOVERNANCE_PASS" if status == "allow" else "GOVERNANCE_FAILURE"],
        "failure_summary": {
            "gate_name": "governance_gate",
            "failure_class": "none" if status == "allow" else "governance_enforcement_failure",
            "root_cause": "none" if status == "allow" else "one or more governance checks failed",
            "blocking_reason": "none" if status == "allow" else "non-zero governance command",
            "next_action": "proceed" if status == "allow" else "inspect command_previews",
            "affected_files": ["docs/governance/required_pr_checks.json", "docs/architecture/system_registry.md"],
            "failed_command": "" if status == "allow" else next((p['cmd'] for p in previews if p['exit_code'] != 0), ""),
            "artifact_refs": ["outputs/required_check_alignment_audit/required_check_alignment_audit_result.json"],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "governance_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "artifact": str(out)}, indent=2))
    return 0 if status == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
