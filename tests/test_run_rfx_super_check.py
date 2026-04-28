from __future__ import annotations

import subprocess

from scripts import run_rfx_super_check as super_check


def test_rt_h15_integrity_and_steps_present():
    original = super_check.subprocess.run

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    super_check.subprocess.run = _fake_run
    try:
        result = super_check.run_rfx_super_check()
    finally:
        super_check.subprocess.run = original

    assert result["status"] == "pass"
    assert set(super_check.REQUIRED_STEPS) == set(result["checks"])
    assert "authority_shape_early_gate" in result["checks"]
