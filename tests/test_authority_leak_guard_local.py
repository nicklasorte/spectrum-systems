"""Local ALG pre-flight: run the authority leak guard over the working branch.

CI already runs ``scripts/run_authority_leak_guard.py`` in the
``artifact-boundary`` workflow, but the failure only surfaces after a PR push.
This test re-runs the same guard from inside the test suite so developers
catch new vocabulary leaks via ``pytest tests/`` before the CI round-trip.

Skips when git history needed for diff resolution is unavailable (fresh
clone without ``origin/main``, sparse checkout, etc.); the CI run remains
authoritative.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = REPO_ROOT / "scripts" / "run_authority_leak_guard.py"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _resolve_base_ref() -> str | None:
    """Find a base ref the guard can diff against; None means skip."""
    for candidate in ("origin/main", "main"):
        if _git("rev-parse", "--verify", f"{candidate}^{{commit}}").returncode == 0:
            return candidate
    parent = _git("rev-parse", "--verify", "HEAD~1^{commit}")
    if parent.returncode == 0:
        return "HEAD~1"
    return None


def _collect_changed_files(base_ref: str) -> list[str]:
    """Union of committed diff, staged, and unstaged working-tree changes.

    The CI guard only sees the committed range; locally we want to flag
    violations the developer is about to commit too, so we widen the set
    to anything dirty in the working tree.
    """
    files: set[str] = set()
    ranges = (
        ["diff", "--name-only", f"{base_ref}..HEAD"],
        ["diff", "--name-only", "--staged"],
        ["diff", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    )
    for cmd in ranges:
        proc = _git(*cmd)
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            path = line.strip()
            if path:
                files.add(path)
    return sorted(files)


def test_authority_leak_guard_passes_on_local_changes(tmp_path: Path) -> None:
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        pytest.skip("not inside a git work tree")

    base_ref = _resolve_base_ref()
    if base_ref is None:
        pytest.skip("no resolvable base ref (origin/main, main, or HEAD~1)")

    changed = _collect_changed_files(base_ref)
    if not changed:
        return

    output_path = tmp_path / "authority_leak_guard_result.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(GUARD_SCRIPT),
            "--base-ref",
            base_ref,
            "--head-ref",
            "HEAD",
            "--changed-files",
            *changed,
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    if proc.returncode == 0:
        return

    detail = proc.stdout + proc.stderr
    if output_path.is_file():
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        violations = payload.get("violations", [])
        rendered = "\n".join(
            f"  {v.get('path')}:{v.get('line')}  {v.get('rule')}  '{v.get('token')}'"
            for v in violations[:20]
        )
        remainder = ""
        if len(violations) > 20:
            remainder = f"\n  ... and {len(violations) - 20} more"
        pytest.fail(
            "Authority leak guard detected new vocabulary violations vs "
            f"{base_ref}. Resolve before pushing — CI will otherwise fail the "
            f"artifact-boundary workflow.\n{rendered}{remainder}"
        )
    pytest.fail(f"authority leak guard exited {proc.returncode}: {detail}")
