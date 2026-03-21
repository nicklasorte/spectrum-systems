#!/usr/bin/env python3
"""Verify local development prerequisites for spectrum-systems.

Checks are intentionally thin and deterministic:
- Python runtime version
- importability of required Python packages
- availability of Node.js runtime
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from dataclasses import dataclass

REQUIRED_PYTHON_PACKAGES = ("jsonschema",)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_python_package(package: str) -> CheckResult:
    try:
        importlib.import_module(package)
    except ModuleNotFoundError:
        return CheckResult(
            name=f"python_package:{package}",
            ok=False,
            detail=f"Missing Python dependency '{package}'. Install with: pip install -r requirements-dev.txt",
        )
    return CheckResult(name=f"python_package:{package}", ok=True, detail=f"Python dependency '{package}' available")


def _check_node_runtime() -> CheckResult:
    node_bin = shutil.which("node")
    if node_bin is None:
        return CheckResult(
            name="node_runtime",
            ok=False,
            detail="Node.js runtime not found in PATH. This repo requires node for cross-repo compliance checks.",
        )

    version = subprocess.run(
        [node_bin, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if version.returncode != 0:
        return CheckResult(
            name="node_runtime",
            ok=False,
            detail="Node.js runtime detected but 'node --version' failed.",
        )

    return CheckResult(name="node_runtime", ok=True, detail=f"Node.js {version.stdout.strip()} available")


def run_checks() -> list[CheckResult]:
    checks = [CheckResult(name="python_runtime", ok=True, detail=f"Python {sys.version.split()[0]} available")]
    checks.extend(_check_python_package(pkg) for pkg in REQUIRED_PYTHON_PACKAGES)
    checks.append(_check_node_runtime())
    return checks


def main() -> int:
    checks = run_checks()
    has_failures = False

    for result in checks:
        prefix = "PASS" if result.ok else "FAIL"
        print(f"[{prefix}] {result.name}: {result.detail}")
        if not result.ok:
            has_failures = True

    if has_failures:
        print("\nEnvironment verification failed. Resolve the FAIL items above before running tests.")
        return 1

    print("\nEnvironment verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
