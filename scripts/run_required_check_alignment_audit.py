#!/usr/bin/env python3
"""Run deterministic required-check alignment audit for PR / pytest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.required_check_alignment_audit import run_required_check_alignment_audit  # noqa: E402


DEFAULT_LOCAL_EVIDENCE_PATHS = [
    ".github/branch_protection_rules.json",
    ".github/required_status_checks.json",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run required-check alignment audit.")
    parser.add_argument("--workflow-path", default=".github/workflows/artifact-boundary.yml")
    parser.add_argument("--policy-path", default="docs/governance/required_pr_checks.json")
    parser.add_argument("--local-evidence-path", action="append", default=[])
    parser.add_argument("--live-github-evidence-path", default="")
    parser.add_argument("--output-dir", default="outputs/required_check_alignment_audit")
    return parser.parse_args()


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"not_object:{path}")
    return payload


def _load_workflow_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    workflow_name_match = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
    workflow_name = workflow_name_match.group(1).strip() if workflow_name_match else "artifact-boundary"
    job_name = ""
    lines = text.splitlines()
    inside_pytest_job = False
    for line in lines:
        if re.match(r"^\s{2}pytest-pr:\s*$", line):
            inside_pytest_job = True
            continue
        if inside_pytest_job and re.match(r"^\s{2}[A-Za-z0-9_.-]+:\s*$", line):
            break
        if inside_pytest_job:
            match = re.match(r"^\s{4}name:\s*(.+?)\s*$", line)
            if match:
                job_name = match.group(1).strip()
                break
    return {"name": workflow_name, "jobs": {"pytest-pr": {"name": job_name}}}


def main() -> int:
    args = _parse_args()
    workflow_path = Path(args.workflow_path) if Path(args.workflow_path).is_absolute() else (REPO_ROOT / args.workflow_path)
    policy_path = Path(args.policy_path) if Path(args.policy_path).is_absolute() else (REPO_ROOT / args.policy_path)

    workflow_payload = _load_workflow_payload(workflow_path)
    policy_payload = _load_json(policy_path)

    candidate_local_paths = args.local_evidence_path or DEFAULT_LOCAL_EVIDENCE_PATHS
    local_payloads: list[dict] = []
    for raw_path in candidate_local_paths:
        path = Path(raw_path) if Path(raw_path).is_absolute() else (REPO_ROOT / raw_path)
        if path.is_file():
            local_payloads.append(_load_json(path))

    live_payload = None
    if args.live_github_evidence_path:
        live_path = Path(args.live_github_evidence_path)
        if not live_path.is_absolute():
            live_path = REPO_ROOT / args.live_github_evidence_path
        if live_path.is_file():
            live_payload = _load_json(live_path)

    result = run_required_check_alignment_audit(
        workflow_payload=workflow_payload,
        required_policy_payload=policy_payload,
        local_required_checks_payloads=local_payloads,
        live_required_checks_payload=live_payload,
    )

    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else (REPO_ROOT / args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "required_check_alignment_audit_result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result_path": str(result_path), "final_decision": result["final_decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
