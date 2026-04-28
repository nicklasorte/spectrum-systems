#!/usr/bin/env python3
"""Canonical Test Selection Gate runner (TST-03/TST-06)."""

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


def _changed_paths(base_ref: str, head_ref: str) -> list[str]:
    if not base_ref or not head_ref:
        return []
    cmd = ["git", "diff", "--name-only", base_ref, head_ref]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical test selection gate")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--output-dir", default="outputs/test_selection_gate")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = json.loads((REPO_ROOT / "docs/governance/pytest_pr_selection_integrity_policy.json").read_text(encoding="utf-8"))
    baseline = json.loads((REPO_ROOT / "docs/governance/pytest_pr_inventory_baseline.json").read_text(encoding="utf-8"))

    changed = _changed_paths(args.base_ref, args.head_ref)
    selected: set[str] = set()
    for path in changed:
        if path.startswith("tests/") and path.endswith(".py"):
            selected.add(path)
        if path.startswith("tests/") and ".test." in path:
            selected.add(path)
        for rule in policy.get("surface_rules", []):
            if path.startswith(rule.get("path_prefix", "")):
                selected.update(rule.get("required_test_targets", []))

    governed = any(path.startswith(tuple(policy.get("governed_surface_prefixes", []))) for path in changed)
    fallback_used = False
    if governed and not selected:
        selected.update(baseline.get("suite_targets", []))
        fallback_used = True

    status = "allow"
    reason_codes = ["SELECTION_OK"]
    if governed and not selected:
        status = "block"
        reason_codes = ["EMPTY_SELECTION_FOR_GOVERNED_SURFACE"]

    result = {
        "artifact_type": "test_selection_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "test_selection_gate",
        "status": status,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_test_selection_gate.py"},
        "provenance": {"base_ref": args.base_ref, "head_ref": args.head_ref},
        "inputs": {"changed_paths": changed, "policy_ref": "docs/governance/pytest_pr_selection_integrity_policy.json"},
        "outputs": {"fallback_used": fallback_used},
        "executed_commands": [f"git diff --name-only {args.base_ref} {args.head_ref}"],
        "selected_tests": sorted(selected),
        "reason_codes": reason_codes,
        "failure_summary": {
            "gate_name": "test_selection_gate",
            "failure_class": "none" if status == "allow" else "selection_integrity_failure",
            "root_cause": "none" if status == "allow" else "governed paths changed without test selection",
            "blocking_reason": "none" if status == "allow" else "empty selected_tests",
            "next_action": "proceed" if status == "allow" else "update selection rules or baseline",
            "affected_files": changed,
            "failed_command": "" if status == "allow" else "git diff --name-only",
            "artifact_refs": ["docs/governance/pytest_pr_selection_integrity_policy.json"],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "test_selection_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "selected_tests": len(selected), "artifact": str(out)}, indent=2))
    return 0 if status == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
