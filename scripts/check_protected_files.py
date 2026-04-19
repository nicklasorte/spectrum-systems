#!/usr/bin/env python3
"""
Pre-push protected file check.
Detects files that require a [GOVERNANCE] PR before shipping.

Two violation classes:
- SHADOW_OWNERSHIP_OVERLAP: modifying system behavior files
- PROTECTED_AUTHORITY_VIOLATION: modifying governance direction files

Usage:
  python scripts/check_protected_files.py --base-ref main --head-ref HEAD

Install as pre-push hook:
  bash scripts/install_hooks.sh
"""

import subprocess
import sys
import argparse
import json

# Files and directories that require a dedicated [GOVERNANCE] PR to modify.
# Feature PRs may not touch these paths.
PROTECTED_FILES = [
    # --- SHADOW_OWNERSHIP_OVERLAP ---
    # These files define system behavior. Changes require a [GOVERNANCE] PR.
    {
        "path": "CLAUDE.md",
        "reason": "Agent configuration document",
        "violation_class": "SHADOW_OWNERSHIP_OVERLAP",
        "change_requires": "governance_pr",
        "example_fix": "git checkout main -- CLAUDE.md",
    },
    {
        "path": "AGENTS.md",
        "reason": "Agent standards document",
        "violation_class": "SHADOW_OWNERSHIP_OVERLAP",
        "change_requires": "governance_pr",
        "example_fix": "git checkout main -- AGENTS.md",
    },
    {
        "path": "scripts/run_system_registry_guard.py",
        "reason": "Registry guard — requires [GOVERNANCE] PR to modify",
        "violation_class": "SHADOW_OWNERSHIP_OVERLAP",
        "change_requires": "governance_pr",
        "example_fix": "Open a [GOVERNANCE] PR",
    },
    {
        "path": ".github/workflows/",
        "reason": "CI/CD pipeline definitions",
        "violation_class": "SHADOW_OWNERSHIP_OVERLAP",
        "change_requires": "governance_pr",
        "example_fix": "Open a [GOVERNANCE] PR to add or modify workflows",
    },
    {
        "path": "contracts/schemas/",
        "reason": "Artifact schema definitions",
        "violation_class": "SHADOW_OWNERSHIP_OVERLAP",
        "change_requires": "governance_pr",
        "example_fix": "Open a [GOVERNANCE] PR with schema migration plan",
    },
    # --- PROTECTED_AUTHORITY_VIOLATION ---
    # These files declare governance direction. Changes require a [GOVERNANCE] PR.
    {
        "path": "docs/roadmaps/",
        "reason": "System roadmap documents",
        "violation_class": "PROTECTED_AUTHORITY_VIOLATION",
        "change_requires": "governance_pr",
        "example_fix": "Open a [GOVERNANCE] PR titled '[GOVERNANCE] Phase X Roadmap'",
    },
    {
        "path": "docs/architecture/",
        "reason": "Architecture decision documents",
        "violation_class": "PROTECTED_AUTHORITY_VIOLATION",
        "change_requires": "governance_pr",
        "example_fix": "Open a [GOVERNANCE] PR following the ADR template",
    },
    {
        "path": "docs/adr/",
        "reason": "Architectural Decision Records",
        "violation_class": "PROTECTED_AUTHORITY_VIOLATION",
        "change_requires": "governance_pr",
        "example_fix": "Open a [GOVERNANCE] PR with new ADR number",
    },
]

# NOTE: This script itself is NOT in the protected list.
# It is safe to ship in a feature PR.
# Only the CI workflow that activates it requires a [GOVERNANCE] PR.


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
    """Return the first protected entry matching file_path, or None."""
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
                "violation_class": entry["violation_class"],
                "change_requires": entry["change_requires"],
                "example_fix": entry.get("example_fix", "Open a [GOVERNANCE] PR"),
            })

    shadow_violations = [v for v in violations if v["violation_class"] == "SHADOW_OWNERSHIP_OVERLAP"]
    authority_violations = [v for v in violations if v["violation_class"] == "PROTECTED_AUTHORITY_VIOLATION"]

    reason_codes = []
    if shadow_violations:
        reason_codes.append("SHADOW_OWNERSHIP_OVERLAP")
    if authority_violations:
        reason_codes.append("PROTECTED_AUTHORITY_VIOLATION")

    return {
        "status": "fail" if violations else "pass",
        "changed_files": changed,
        "violations": violations,
        "reason_codes": reason_codes,
    }


def print_report(result: dict) -> None:
    print(json.dumps({
        "status": result["status"],
        "changed_files": result["changed_files"],
        "violations": [
            {
                "file": v["file"],
                "reason": v["reason"],
                "violation_class": v["violation_class"],
                "change_requires": v["change_requires"],
            }
            for v in result["violations"]
        ],
        "reason_codes": result["reason_codes"],
    }, indent=2))

    if result["status"] == "fail":
        print("\n❌ Protected file violation detected!", file=sys.stderr)
        for v in result["violations"]:
            print(f"\n  File    : {v['file']}", file=sys.stderr)
            print(f"  Reason  : {v['reason']}", file=sys.stderr)
            print(f"  Requires: {v['change_requires']}", file=sys.stderr)
            print(f"  Fix     : {v['example_fix']}", file=sys.stderr)
        print(
            "\nProtected files must ship via a dedicated [GOVERNANCE] PR.",
            file=sys.stderr,
        )
    else:
        print("✅ Protected file check passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for protected file violations")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--output", required=False)
    args = parser.parse_args()

    result = run_check(args.base_ref, args.head_ref)
    print_report(result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)

    sys.exit(1 if result["status"] == "fail" else 0)
