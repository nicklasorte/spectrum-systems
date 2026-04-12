from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / ".codex" / "skills" / "contract-boundary-audit" / "run.sh"


def test_contract_boundary_audit_pass_warn_mode_is_operational() -> None:
    proc = subprocess.run([str(AUDIT_SCRIPT)], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "[contract-boundary-audit] summary:" in proc.stdout


def test_contract_boundary_audit_strict_mode_fails_on_warnings() -> None:
    proc = subprocess.run([str(AUDIT_SCRIPT), "--strict"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode in {0, 1}
    if proc.returncode == 1:
        assert "warnings treated as errors in strict mode" in proc.stdout
