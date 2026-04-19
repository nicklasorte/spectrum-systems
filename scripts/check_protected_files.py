#!/usr/bin/env python3
"""
Pre-PR protected file check
Run this before pushing to catch SHADOW_OWNERSHIP_OVERLAP early
Usage: python scripts/check_protected_files.py --base-ref main --head-ref HEAD
"""

import subprocess
import sys
import argparse
import json

PROTECTED_FILES = [
    {
        "path": "CLAUDE.md",
        "reason": "Agent authority document",
        "change_requires": "governance_pr"
    },
    {
        "path": "AGENTS.md",
        "reason": "Agent standards document",
        "change_requires": "governance_pr"
    },
    {
        "path": "scripts/run_system_registry_guard.py",
        "reason": "Registry guard is authority enforcement",
        "change_requires": "governance_pr"
    },
    {
        "path": ".github/workflows/",
        "reason": "CI/CD pipelines",
        "change_requires": "governance_pr"
    },
    {
        "path": "contracts/schemas/",
        "reason": "Core artifact schemas",
        "change_requires": "governance_pr"
    },
]


def get_changed_files(base_ref: str, head_ref: str):
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, head_ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}", file=sys.stderr)
        return []


def is_protected(file_path: str):
    for protected in PROTECTED_FILES:
        if protected["path"].endswith("/"):
            if file_path.startswith(protected["path"]):
                return protected
        else:
            if file_path == protected["path"]:
                return protected
    return None


def check_files(base_ref: str, head_ref: str):
    changed = get_changed_files(base_ref, head_ref)
    violations = []

    for file in changed:
        protected = is_protected(file)
        if protected:
            violations.append({
                "file": file,
                "reason": protected["reason"],
                "change_requires": protected["change_requires"],
            })

    return {
        "status": "fail" if violations else "pass",
        "changed_files": changed,
        "violations": violations,
        "reason_codes": ["SHADOW_OWNERSHIP_OVERLAP"] if violations else [],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--output", required=False)
    args = parser.parse_args()

    result = check_files(args.base_ref, args.head_ref)
    output = json.dumps(result, indent=2)
    print(output)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)

    if result["status"] == "fail":
        print("\n❌ SHADOW_OWNERSHIP_OVERLAP detected!", file=sys.stderr)
        for v in result["violations"]:
            print(f"   {v['file']}: {v['reason']}", file=sys.stderr)
        print("\nFix: git checkout main -- CLAUDE.md AGENTS.md", file=sys.stderr)
        sys.exit(1)

    print("✅ Protected file check passed")
    sys.exit(0)
