#!/usr/bin/env python3
"""
Pre-push protected file check.
Catches SHADOW_OWNERSHIP_OVERLAP before it reaches CI.

Usage:
  python scripts/check_protected_files.py --base-ref main --head-ref HEAD
  python scripts/check_protected_files.py --base-ref f8c7bfe --head-ref 6f40e63

Install as pre-push hook:
  bash scripts/install_hooks.sh
"""

import subprocess
import sys
import argparse
import json

# Files/directories that CANNOT be modified via feature PRs.
# Changes to these require a dedicated governance PR.
#
# IMPORTANT: This script itself (check_protected_files.py) is NOT protected —
# it is safe to ship in a feature PR. Only the CI workflow that wires it into
# GitHub Actions requires a governance PR.
PROTECTED_FILES = [
    {
        "path": "CLAUDE.md",
        "reason": "Agent authority document — defines agent behavior and system standards",
        "change_requires": "governance_pr",
        "example_fix": "git checkout main -- CLAUDE.md",
    },
    {
        "path": "AGENTS.md",
        "reason": "Agent standards document — injected agent memory per Canonical Harness spec",
        "change_requires": "governance_pr",
        "example_fix": "git checkout main -- AGENTS.md",
    },
    {
        "path": "scripts/run_system_registry_guard.py",
        "reason": "Registry guard enforcement — cannot be self-modified via feature PR",
        "change_requires": "governance_pr",
        "example_fix": "Open a governance PR titled [GOVERNANCE] ...",
    },
    {
        "path": ".github/workflows/",
        "reason": "CI/CD pipelines — changes affect all builds and enforcement gates",
        "change_requires": "governance_pr",
        "example_fix": "Open a governance PR titled [GOVERNANCE] to add or modify workflows",
        # NOTE: check_protected_files.py itself is NOT in this list.
        # The workflow that wires it into CI (.github/workflows/) IS protected.
        # The script is safe in feature PRs.
    },
    {
        "path": "contracts/schemas/",
        "reason": "Core artifact schemas — changes can break backward compatibility",
        "change_requires": "governance_pr",
        "example_fix": "Open a governance PR with schema migration plan",
    },
]


def get_changed_files(base_ref: str, head_ref: str) -> list[str]:
    """Get list of files changed between base and head refs."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, head_ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except subprocess.CalledProcessError as e:
        print(f"Warning: could not diff {base_ref}..{head_ref}: {e}", file=sys.stderr)
        return []


def find_violation(file_path: str) -> dict | None:
    """Return the first protected entry that matches file_path, or None."""
    for entry in PROTECTED_FILES:
        pattern = entry["path"]
        if pattern.endswith("/"):
            if file_path.startswith(pattern):
                return entry
        else:
            if file_path == pattern:
                return entry
    return None


def run_check(base_ref: str, head_ref: str) -> dict:
    changed = get_changed_files(base_ref, head_ref)
    violations = []

    for file in changed:
        entry = find_violation(file)
        if entry:
            violations.append({
                "file": file,
                "reason": entry["reason"],
                "change_requires": entry["change_requires"],
                "example_fix": entry.get("example_fix", "Open a governance PR"),
            })

    return {
        "status": "fail" if violations else "pass",
        "changed_files": changed,
        "violations": violations,
        "reason_codes": ["SHADOW_OWNERSHIP_OVERLAP"] if violations else [],
    }


def print_report(result: dict) -> None:
    print(json.dumps({
        "status": result["status"],
        "changed_files": result["changed_files"],
        "violations": [
            {"file": v["file"], "reason": v["reason"], "change_requires": v["change_requires"]}
            for v in result["violations"]
        ],
        "reason_codes": result["reason_codes"],
    }, indent=2))

    if result["status"] == "fail":
        print("\n❌ SHADOW_OWNERSHIP_OVERLAP detected!", file=sys.stderr)
        for v in result["violations"]:
            print(f"\n  File    : {v['file']}", file=sys.stderr)
            print(f"  Reason  : {v['reason']}", file=sys.stderr)
            print(f"  Requires: {v['change_requires']}", file=sys.stderr)
            print(f"  Fix     : {v['example_fix']}", file=sys.stderr)
        print(
            "\nProtected files must ship in a dedicated [GOVERNANCE] PR, not a feature PR.",
            file=sys.stderr,
        )
    else:
        print("✅ Protected file check passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for protected file violations")
    parser.add_argument("--base-ref", required=True, help="Base git ref (e.g. main or commit SHA)")
    parser.add_argument("--head-ref", required=True, help="Head git ref (e.g. HEAD or commit SHA)")
    parser.add_argument("--output", required=False, help="Write JSON result to this path")
    args = parser.parse_args()

    result = run_check(args.base_ref, args.head_ref)
    print_report(result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)

    sys.exit(1 if result["status"] == "fail" else 0)
