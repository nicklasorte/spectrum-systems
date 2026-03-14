#!/usr/bin/env python3
"""
Fail CI when prohibited artifacts or large binaries are present.
Enforces data-boundary rules that keep operational artifacts out of GitHub.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BANNED_EXTS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".rtf",
    ".msg",
    ".eml",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".rar",
    ".bin",
    ".sqlite",
    ".db",
}

ALLOWED_PREFIXES = (
    "examples/",
    "contracts/examples/",
    "tests/fixtures/",
)

SIZE_THRESHOLD_BYTES = 2 * 1024 * 1024  # 2 MB


def is_allowed_fixture(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def list_repo_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_files(files: list[str]) -> list[str]:
    violations: list[str] = []
    for path in files:
        if not path or not os.path.isfile(path):
            continue
        _, ext = os.path.splitext(path.lower())
        if ext in BANNED_EXTS and not is_allowed_fixture(path):
            violations.append(
                f"{path}: prohibited extension {ext} (see docs/data-boundary-governance.md)"
            )
            continue

        if not is_allowed_fixture(path):
            size = Path(path).stat().st_size
            if size > SIZE_THRESHOLD_BYTES:
                violations.append(
                    f"{path}: size {size} bytes exceeds {SIZE_THRESHOLD_BYTES} byte limit for in-repo files"
                )
    return violations


def main() -> int:
    files = list_repo_files()
    violations = check_files(files)
    if violations:
        print("Artifact boundary violations detected:")
        for violation in violations:
            print(f" - {violation}")
        print(
            "Operational artifacts must stay on external storage. "
            "If this is a synthetic fixture, place it under examples/ or tests/fixtures/."
        )
        return 1

    print("Artifact boundary check passed: no prohibited binary or oversized artifacts tracked in Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
