#!/usr/bin/env python3
"""Run deterministic System Registry Guard (SRG) checks over changed files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.system_registry_guard import (  # noqa: E402
    SystemRegistryGuardError,
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)


def _run(command: list[str]) -> tuple[int, str]:
    proc = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip() or proc.stderr.strip()


def _resolve_changed_files(base_ref: str, head_ref: str, explicit: list[str]) -> list[str]:
    if explicit:
        return sorted(set(path.strip() for path in explicit if path.strip()))
    zero_sha = "0" * 40
    if base_ref == zero_sha:
        code, output = _run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", head_ref])
        if code != 0:
            raise SystemRegistryGuardError(f"failed to resolve changed files from head commit {head_ref}: {output}")
        return sorted(set(line.strip() for line in output.splitlines() if line.strip()))
    code, output = _run(["git", "diff", "--name-only", f"{base_ref}..{head_ref}"])
    if code != 0:
        raise SystemRegistryGuardError(f"failed to resolve changed files from {base_ref}..{head_ref}: {output}")
    return sorted(set(line.strip() for line in output.splitlines() if line.strip()))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed system registry ownership guard")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--output",
        default="outputs/system_registry_guard/system_registry_guard_result.json",
        help="Output artifact path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    changed_files = _resolve_changed_files(args.base_ref, args.head_ref, list(args.changed_files or []))

    policy = load_guard_policy(REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json")
    registry = parse_system_registry(REPO_ROOT / "docs" / "architecture" / "system_registry.md")
    result = evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        policy=policy,
        registry_model=registry,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": result["status"],
                "changed_files": result["changed_files"],
                "reason_codes": result["normalized_reason_codes"],
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
