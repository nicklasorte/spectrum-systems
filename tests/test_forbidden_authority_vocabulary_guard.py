from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_authority_vocabulary_guard_passes_transcript_surfaces() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/validate_forbidden_authority_vocabulary.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_forbidden_authority_vocabulary_guard_flags_non_owner_file(tmp_path: Path) -> None:
    violator = tmp_path / "violator.py"
    violator.write_text("payload = {'decision': 'allow'}\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/validate_forbidden_authority_vocabulary.py",
            "--scan-path",
            str(violator),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "forbidden authority key 'decision'" in (proc.stdout + proc.stderr)


def test_system_registry_guard_passes_transcript_architecture_boundary_doc() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/run_system_registry_guard.py",
            "--changed-files",
            "docs/architecture/transcript_processing_hardening.md",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_authority_leak_guard_passes_transcript_boundary_doc() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/run_authority_leak_guard.py",
            "--changed-files",
            "docs/architecture/transcript_processing_hardening.md",
            "--output",
            "outputs/authority_leak_guard/test_transcript_boundary_doc.json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
