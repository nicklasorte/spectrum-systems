"""Build dashboard-3ls with fail-closed TLS artifact generation.

Usage:
    python scripts/build_dashboard_3ls_with_tls.py [--skip-next-build]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


CANDIDATES = "H01,RFX,HOP,MET,METS"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def dashboard_dir() -> Path:
    return repo_root() / "apps" / "dashboard-3ls"


def artifact_path() -> Path:
    return repo_root() / "artifacts" / "system_dependency_priority_report.json"


def _run(cmd: list[str], cwd: Path) -> int:
    completed = subprocess.run(cmd, cwd=str(cwd), env=dict(os.environ), check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-next-build",
        action="store_true",
        help="Generate/verify TLS artifacts only; do not invoke next build.",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    tls_cmd = [
        sys.executable,
        "scripts/build_tls_dependency_priority.py",
        "--candidates",
        CANDIDATES,
        "--fail-if-missing",
    ]
    tls_rc = _run(tls_cmd, cwd=root)
    if tls_rc != 0:
        return tls_rc

    artifact = artifact_path()
    if not artifact.is_file():
        print(
            f"FAIL: required artifact missing after TLS build: {artifact}",
            file=sys.stderr,
        )
        return 1

    if args.skip_next_build:
        return 0

    next_rc = _run(["next", "build"], cwd=dashboard_dir())
    if next_rc != 0:
        return next_rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
