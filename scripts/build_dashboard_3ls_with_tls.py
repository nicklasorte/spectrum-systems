"""Build dashboard-3ls with fail-closed TLS artifact generation.

Usage:
    python scripts/build_dashboard_3ls_with_tls.py [--skip-next-build] [--skip-next-step]
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


def next_step_artifact_path() -> Path:
    return repo_root() / "artifacts" / "next_step_decision_report.json"


def registry_path() -> Path:
    return repo_root() / "docs" / "architecture" / "system_registry.md"


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    completed = subprocess.run(cmd, cwd=str(cwd), env=env or dict(os.environ), check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-next-build",
        action="store_true",
        help="Generate/verify governance artifacts only; do not invoke next build.",
    )
    parser.add_argument(
        "--skip-next-step",
        action="store_true",
        help="Skip next-step artifact generation (local debug only).",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    dash = dashboard_dir()
    artifact = artifact_path()
    next_step_artifact = next_step_artifact_path()
    registry = registry_path()
    tls_env = dict(os.environ)
    tls_env["PYTHONPATH"] = str(root)

    print(f"[dashboard-3ls-build] repo_root={root}", flush=True)
    print(f"[dashboard-3ls-build] dashboard_dir={dash}", flush=True)
    print(f"[dashboard-3ls-build] PYTHONPATH={tls_env['PYTHONPATH']}", flush=True)
    print(f"[dashboard-3ls-build] expected_registry={registry}", flush=True)
    print(f"[dashboard-3ls-build] expected_artifact={artifact}", flush=True)

    if not registry.is_file():
        print(f"FAIL: required TLS registry input missing at {registry}", file=sys.stderr)
        print(
            "FAIL: .vercelignore likely excluded required TLS registry input",
            file=sys.stderr,
        )
        return 1

    tls_cmd = [
        sys.executable,
        str(root / "scripts" / "build_tls_dependency_priority.py"),
        "--candidates",
        CANDIDATES,
        "--fail-if-missing",
    ]
    print(f"[dashboard-3ls-build] tls_command={' '.join(tls_cmd)}", flush=True)
    tls_rc = _run(tls_cmd, cwd=root, env=tls_env)
    if tls_rc != 0:
        return tls_rc

    if not artifact.is_file():
        print(
            f"FAIL: required artifact missing after TLS build: {artifact}",
            file=sys.stderr,
        )
        return 1

    if not args.skip_next_step:
        next_step_cmd = [sys.executable, str(root / "scripts" / "build_next_step_decision.py")]
        print(f"[dashboard-3ls-build] next_step_command={' '.join(next_step_cmd)}", flush=True)
        next_step_rc = _run(next_step_cmd, cwd=root, env=tls_env)
        if next_step_rc != 0:
            return next_step_rc

        if not next_step_artifact.is_file():
            print(
                f"FAIL: required artifact missing after next-step build: {next_step_artifact}",
                file=sys.stderr,
            )
            return 1

    if args.skip_next_build:
        return 0

    next_cmd = ["npm", "exec", "--", "next", "build"]
    print(f"[dashboard-3ls-build] next_command={' '.join(next_cmd)}", flush=True)
    next_rc = _run(next_cmd, cwd=dash)
    if next_rc != 0:
        return next_rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
