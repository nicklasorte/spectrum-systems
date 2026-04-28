#!/usr/bin/env python3
"""Thin canonical PR gate orchestrator (TST-04)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ORDER = [
    ("contract_gate", "scripts/run_contract_gate.py", "outputs/contract_gate/contract_gate_result.json"),
    ("test_selection_gate", "scripts/run_test_selection_gate.py", "outputs/test_selection_gate/test_selection_gate_result.json"),
    ("runtime_test_gate", "scripts/run_runtime_test_gate.py", "outputs/runtime_test_gate/runtime_test_gate_result.json"),
    ("governance_gate", "scripts/run_governance_gate.py", "outputs/governance_gate/governance_gate_result.json"),
    ("certification_gate", "scripts/run_certification_gate.py", "outputs/certification_gate/certification_gate_result.json"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PR canonical gates")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--output-dir", default="outputs/pr_gate")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    gate_results = []
    executed = []
    overall = "allow"
    for gate_name, script, artifact_ref in ORDER:
        cmd = [sys.executable, script]
        if gate_name in {"contract_gate", "test_selection_gate"}:
            cmd.extend(["--base-ref", args.base_ref, "--head-ref", args.head_ref])
        if gate_name == "runtime_test_gate":
            cmd.extend(["--selection-artifact", "outputs/test_selection_gate/test_selection_gate_result.json"])
        code, stdout, stderr = _run(cmd)
        executed.append(" ".join(cmd))
        artifact_path = REPO_ROOT / artifact_ref
        payload = {"status": "block", "reason_codes": ["MISSING_ARTIFACT"]}
        if artifact_path.is_file():
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        payload.setdefault("stdout_preview", stdout[-300:])
        payload.setdefault("stderr_preview", stderr[-300:])
        gate_results.append({"gate_name": gate_name, "status": payload.get("status", "block"), "artifact_ref": artifact_ref, "reason_codes": payload.get("reason_codes", []), "exit_code": code})
        if code != 0 or payload.get("status") != "allow":
            overall = "block"
            break

    result = {
        "artifact_type": "pr_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "pr_gate",
        "status": overall,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_pr_gate.py"},
        "provenance": {"base_ref": args.base_ref, "head_ref": args.head_ref},
        "inputs": {"gate_order": [g[0] for g in ORDER]},
        "outputs": {"gate_results": gate_results},
        "executed_commands": executed,
        "selected_tests": [],
        "reason_codes": ["PR_GATE_ALLOW" if overall == "allow" else "PR_GATE_BLOCK"],
        "failure_summary": {
            "gate_name": "pr_gate",
            "failure_class": "none" if overall == "allow" else "canonical_gate_block",
            "root_cause": "none" if overall == "allow" else next((g['gate_name'] for g in gate_results if g['status'] != 'allow'), "unknown"),
            "blocking_reason": "none" if overall == "allow" else "at least one gate blocked",
            "next_action": "proceed" if overall == "allow" else "inspect first blocked gate artifact",
            "affected_files": [],
            "failed_command": "" if overall == "allow" else executed[-1],
            "artifact_refs": [g["artifact_ref"] for g in gate_results],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "pr_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": overall, "artifact": str(out)}, indent=2))
    return 0 if overall == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
