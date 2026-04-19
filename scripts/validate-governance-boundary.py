#!/usr/bin/env python3
"""
Validates that spectrum-systems is GOVERNANCE-ONLY: no production code,
only contracts, schemas, and governance documentation.

Blocks commits introducing disallowed file types per
ecosystem/spectrum-systems.file-types.schema.json
"""

import json
import sys
import os
from pathlib import Path
from fnmatch import fnmatch

def load_schema():
    """Load the allowed file types schema."""
    schema_path = Path("ecosystem/spectrum-systems.file-types.schema.json")
    if not schema_path.exists():
        print(f"❌ ERROR: Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path) as f:
        return json.load(f)

def flatten_patterns(pattern_list):
    """Flatten nested pattern lists."""
    result = []
    for item in pattern_list:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and "pattern" in item:
            result.append(item["pattern"])
    return result

def should_check_file(file_path):
    """Determine if file should be checked (skip git, venv, etc)."""
    parts = file_path.parts

    # Skip hidden directories and common exclusions
    skip_dirs = {".git", ".venv", "venv", ".env", "node_modules", "__pycache__", ".pytest_cache"}
    if any(part in skip_dirs for part in parts):
        return False

    # Skip hidden files at root
    if file_path.name.startswith(".") and file_path.name not in {".gitignore", ".github"}:
        return False

    return True

def check_forbidden_patterns(file_path, forbidden_list):
    """Check if file matches any forbidden pattern."""
    for forbidden in forbidden_list:
        pattern = forbidden.get("pattern") if isinstance(forbidden, dict) else forbidden
        if fnmatch(str(file_path), pattern):
            return forbidden
    return None

def check_allowed_patterns(file_path, allowed_lists):
    """Check if file matches any allowed pattern."""
    for pattern_list in allowed_lists.values():
        if isinstance(pattern_list, list):
            for pattern in pattern_list:
                if fnmatch(str(file_path), pattern):
                    return True
    return False

def validate_governance_boundary():
    """Validate all files against schema."""
    schema = load_schema()

    allowed_patterns_dict = schema.get("properties", {}).get("allowed_file_types", {}).get("properties", {})
    forbidden_patterns = schema.get("properties", {}).get("forbidden_patterns", {}).get("default", [])
    exceptions = schema.get("properties", {}).get("exceptions", {}).get("default", [])

    violations = []
    checked_files = 0

    # Scan all files
    for file_path in Path(".").rglob("*"):
        if file_path.is_dir():
            continue

        if not should_check_file(file_path):
            continue

        checked_files += 1

        # Check forbidden patterns first (strict)
        forbidden = check_forbidden_patterns(file_path, forbidden_patterns)
        if forbidden:
            # Check if there's an exception
            exception_found = False
            for exception in exceptions:
                if fnmatch(str(file_path), exception.get("pattern", "")):
                    exception_found = True
                    break

            if not exception_found:
                violations.append({
                    "file": file_path,
                    "reason": forbidden.get("reason") if isinstance(forbidden, dict) else "Forbidden pattern",
                    "severity": forbidden.get("severity", "HIGH") if isinstance(forbidden, dict) else "HIGH"
                })
                continue

        # Check if file is in allowed patterns
        if not check_allowed_patterns(file_path, allowed_patterns_dict):
            violations.append({
                "file": file_path,
                "reason": "File type not in allowed patterns",
                "severity": "MEDIUM"
            })

    return checked_files, violations

def main():
    """Main validation routine."""
    print("Validating governance boundary for spectrum-systems...")
    print("=" * 70)

    checked_files, violations = validate_governance_boundary()

    # Sort violations by severity
    violations.sort(key=lambda v: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}.get(v["severity"], 3))

    print(f"Checked {checked_files} files")

    if violations:
        print(f"\n❌ Found {len(violations)} governance boundary violations:\n")

        # Group by severity
        critical = [v for v in violations if v["severity"] == "CRITICAL"]
        high = [v for v in violations if v["severity"] == "HIGH"]
        medium = [v for v in violations if v["severity"] == "MEDIUM"]

        if critical:
            print(f"🛑 CRITICAL ({len(critical)}):")
            for v in critical[:10]:
                print(f"  {v['file']}: {v['reason']}")
            if len(critical) > 10:
                print(f"  ... and {len(critical) - 10} more")

        if high:
            print(f"\n⚠️  HIGH ({len(high)}):")
            for v in high[:10]:
                print(f"  {v['file']}: {v['reason']}")
            if len(high) > 10:
                print(f"  ... and {len(high) - 10} more")

        if medium:
            print(f"\n⚡ MEDIUM ({len(medium)}):")
            for v in medium[:5]:
                print(f"  {v['file']}: {v['reason']}")
            if len(medium) > 5:
                print(f"  ... and {len(medium) - 5} more")

        print("\n" + "=" * 70)
        print("Resolution:")
        print("  1. Review spectrum-systems.file-types.schema.json for allowed patterns")
        print("  2. Move disallowed files to dedicated implementation repositories")
        print("  3. Document exceptions in schema (with expiry date)")
        print("  4. See docs/phase-16-implementation-plan.md for detailed guidance")

        return 1
    else:
        print("\n✅ Governance boundary validation PASSED")
        print("   spectrum-systems is governance-only (no production code)")
        return 0

if __name__ == "__main__":
    sys.exit(main())
