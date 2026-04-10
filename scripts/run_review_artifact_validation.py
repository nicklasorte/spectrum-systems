#!/usr/bin/env python3
"""Canonical review-artifact validation entrypoint (PQX execution, SEL enforcement)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, check=False)
    return {
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout_excerpt": (completed.stdout or "")[-4000:],
        "stderr_excerpt": (completed.stderr or "")[-4000:],
    }


def run_review_artifact_validation(*, repo_root: Path, narrow_test_targets: list[str] | None = None) -> dict[str, Any]:
    """Execute canonical review artifact validation commands."""
    commands: list[list[str]] = [
        ["npm", "install", "--no-save", "--no-package-lock", "ajv@^8", "ajv-formats@^2"],
        ["node", "scripts/validate-review-artifacts.js"],
        ["python", "-m", "pip", "install", "-r", "requirements-dev.txt"],
        ["python", "scripts/check_review_registry.py", "--fail-on-overdue"],
    ]
    if narrow_test_targets:
        commands.append(["pytest", *narrow_test_targets])
        validation_scope = "narrow"
    else:
        commands.append(["pytest"])
        validation_scope = "full"

    command_results = [_run_command(command, cwd=repo_root) for command in commands]
    passed = all(result["exit_code"] == 0 for result in command_results)

    return {
        "artifact_type": "validation_result_record",
        "validation_result_id": "",
        "attempt_id": "",
        "admission_ref": "",
        "trace_id": "",
        "enforcement_owner": "SEL",
        "execution_owner": "PQX",
        "workflow_equivalent": "review-artifact-validation",
        "validation_scope": validation_scope,
        "validation_target": {"type": "repo_branch", "value": ""},
        "validation_path": "pre_push_replay",
        "status": "passed" if passed else "failed",
        "blocking_reason": None if passed else "validation_command_failed",
        "failure_summary": None if passed else "One or more replay commands failed.",
        "commands": command_results,
        "passed": passed,
        "emitted_at": _utc_now(),
    }


def _parse_targets(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    targets = [entry.strip() for entry in raw.split(",") if entry.strip()]
    return targets or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run canonical review artifact validation commands.")
    parser.add_argument("--repo-root", default=".", help="Repository root where commands execute.")
    parser.add_argument("--targets", help="Optional comma-separated pytest targets for narrow replay.")
    parser.add_argument("--output-json", help="Optional output path for validation_result_record JSON.")
    parser.add_argument(
        "--allow-full-pytest",
        action="store_true",
        help="Require explicit opt-in when no narrow targets are provided.",
    )
    args = parser.parse_args(argv)

    targets = _parse_targets(args.targets)
    if targets is None and not args.allow_full_pytest:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "full_pytest_not_explicitly_allowed",
                    "hint": "Pass --allow-full-pytest for CI/full replay or --targets for narrow replay.",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    result = run_review_artifact_validation(repo_root=Path(args.repo_root), narrow_test_targets=targets)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
