#!/usr/bin/env python3
"""
Governance boundary validator for spectrum-systems.

Verifies spectrum-systems is a governance-only repo:
- No production Python source code
- No implementation artifacts
- Contains only: contracts, schemas, governance docs, boundary scripts

Phase 16 deliverable.
"""

import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories that must not exist or must be empty of production code
FORBIDDEN_DIRS = [
    "spectrum_systems",
    "src/mvp-integration",
    "src/observability",
    "src/governance",
    "src/replay",
    "src/trace",
    "src/signing",
    "src/judgment",
    "src/policy",
    "control_plane",
    "working_paper_generator",
]

# File patterns that must not exist
FORBIDDEN_PATTERNS = [
    "*.ts",
    "*.js",
    "package.json",
    "tsconfig.json",
]

# Allowed Python files (by path prefix)
ALLOWED_PYTHON_PREFIXES = [
    "tests/",
    "scripts/",
]


def check_forbidden_dirs():
    """Check for forbidden directories with production code."""
    violations = []
    for dir_name in FORBIDDEN_DIRS:
        dir_path = REPO_ROOT / dir_name
        if dir_path.exists():
            py_files = list(dir_path.rglob("*.py"))
            ts_files = list(dir_path.rglob("*.ts"))
            all_files = py_files + ts_files
            if all_files:
                violations.append({
                    "type": "forbidden_directory",
                    "path": str(dir_name),
                    "file_count": len(all_files),
                    "example": str(all_files[0].relative_to(REPO_ROOT)) if all_files else None,
                    "fix": f"Remove {dir_name}/ or move to dedicated engine repo",
                })
    return violations


def check_forbidden_patterns():
    """Check for forbidden file patterns."""
    violations = []
    for pattern in FORBIDDEN_PATTERNS:
        matches = [
            f for f in REPO_ROOT.rglob(pattern)
            if ".git" not in str(f) and "node_modules" not in str(f)
        ]
        for match in matches:
            violations.append({
                "type": "forbidden_pattern",
                "path": str(match.relative_to(REPO_ROOT)),
                "pattern": pattern,
                "fix": "Remove or move to dedicated repo",
            })
    return violations


def check_production_code_in_scripts():
    """Check for production code patterns in Python files."""
    violations = []
    forbidden_code_patterns = [
        "class Engine",
        "class Executor",
        "def execute_pipeline",
        "def run_orchestration",
    ]
    for py_file in REPO_ROOT.rglob("*.py"):
        rel = py_file.relative_to(REPO_ROOT)
        # Skip allowed locations
        if any(str(rel).startswith(prefix) for prefix in ALLOWED_PYTHON_PREFIXES):
            continue
        if ".git" in str(rel):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for pattern in forbidden_code_patterns:
            if pattern in content:
                violations.append({
                    "type": "production_code_pattern",
                    "path": str(rel),
                    "pattern": pattern,
                    "fix": "Move to dedicated engine repo",
                })
    return violations


def main():
    """Run all boundary checks."""
    all_violations = []
    all_violations.extend(check_forbidden_dirs())
    all_violations.extend(check_forbidden_patterns())
    all_violations.extend(check_production_code_in_scripts())

    result = {
        "status": "fail" if all_violations else "pass",
        "violation_count": len(all_violations),
        "violations": all_violations,
    }

    print(json.dumps(result, indent=2))

    if all_violations:
        print(f"\n❌ {len(all_violations)} governance boundary violations found.", file=sys.stderr)
        print("This repo must be governance-only (contracts, schemas, docs).", file=sys.stderr)
        return 1

    print("✅ Governance boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
