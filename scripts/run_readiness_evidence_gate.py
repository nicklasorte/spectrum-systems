#!/usr/bin/env python3
"""Done-readiness evidence gate runner for PR and deep checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ARTIFACTS = [
    "outputs/contract_gate/contract_gate_result.json",
    "outputs/runtime_test_gate/runtime_test_gate_result.json",
    "outputs/governance_gate/governance_gate_result.json",
]
DEEP_REQUIRED_PATH_PREFIXES = (
    "spectrum_systems/modules/runtime/replay",
    "spectrum_systems/modules/runtime/lineage",
    "scripts/run_replay",
    "scripts/run_lineage",
)
DEEP_EVIDENCE_REF = "outputs/gov10_readiness/gov10_input_record.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _changed_paths(base_ref: str, head_ref: str) -> list[str]:
    if not base_ref or not head_ref:
        return []
    proc = subprocess.run(["git", "diff", "--name-only", base_ref, head_ref], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run readiness evidence gate")
    parser.add_argument("--output-dir", default="outputs/readiness_evidence_gate")
    parser.add_argument("--mode", choices=["pr", "deep"], default="pr")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    changed = _changed_paths(args.base_ref, args.head_ref)
    missing = [p for p in REQUIRED_ARTIFACTS if not (REPO_ROOT / p).is_file()]
    deep_path_touched = any(path.startswith(DEEP_REQUIRED_PATH_PREFIXES) for path in changed)
    require_deep_evidence = args.mode == "deep" or deep_path_touched

    deep_evidence_missing = require_deep_evidence and not (REPO_ROOT / DEEP_EVIDENCE_REF).is_file()
    status = "allow" if not missing and not deep_evidence_missing else "block"
    reason_codes = ["READINESS_EVIDENCE_OK" if status == "allow" else "READINESS_EVIDENCE_BLOCK"]

    result = {
        "artifact_type": "readiness_evidence_gate_result",
        "schema_version": "1.0.0",
        "gate_name": "readiness_evidence_gate",
        "status": status,
        "trace": {"produced_at": _utc_now(), "producer_script": "scripts/run_readiness_evidence_gate.py"},
        "provenance": {"mode": args.mode, "base_ref": args.base_ref, "head_ref": args.head_ref},
        "inputs": {
            "required_artifacts": REQUIRED_ARTIFACTS,
            "changed_paths": changed,
            "require_deep_evidence": require_deep_evidence,
            "deep_evidence_ref": DEEP_EVIDENCE_REF,
        },
        "outputs": {
            "missing_required_artifacts": missing,
            "deep_evidence_missing": deep_evidence_missing,
        },
        "executed_commands": [f"git diff --name-only {args.base_ref} {args.head_ref}"],
        "selected_tests": [],
        "reason_codes": reason_codes,
        "failure_summary": {
            "gate_name": "readiness_evidence_gate",
            "failure_class": "none" if status == "allow" else "readiness_evidence_failure",
            "root_cause": "none" if status == "allow" else ("missing required upstream artifacts" if missing else "missing deep readiness evidence"),
            "blocking_reason": "none" if status == "allow" else (", ".join(missing) if missing else DEEP_EVIDENCE_REF),
            "next_action": "proceed" if status == "allow" else "populate required evidence and rerun",
            "affected_files": changed,
            "failed_command": "" if status == "allow" else "readiness evidence validation",
            "artifact_refs": REQUIRED_ARTIFACTS + [DEEP_EVIDENCE_REF],
        },
    }
    result["artifact_hash"] = _hash_payload(result)
    out = output_dir / "readiness_evidence_gate_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "artifact": str(out)}, indent=2))
    return 0 if status in {"allow", "warn"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
