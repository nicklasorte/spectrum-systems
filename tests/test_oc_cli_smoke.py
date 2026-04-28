"""OC CLI smoke tests — exercise the five required CLIs end to end."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*args, expect_codes=(0,)):
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert (
        result.returncode in expect_codes
    ), f"unexpected exit code {result.returncode}; stderr={result.stderr}; stdout={result.stdout}"
    return result


def test_run_fast_trust_gate_cli_passes_on_default_manifest():
    _run("scripts/run_fast_trust_gate.py")


def test_print_operational_closure_with_no_inputs_returns_unknown():
    # No JSON inputs -> overall_status = unknown -> exit 3
    _run("scripts/print_operational_closure.py", expect_codes=(3,))


def test_generate_dashboard_truth_projection_no_inputs_returns_unknown():
    # No inputs => alignment_status = unknown => exit 2
    _run(
        "scripts/generate_dashboard_truth_projection.py",
        expect_codes=(2,),
    )


def test_generate_artifact_cleanup_candidates_with_simple_input(tmp_path: Path):
    candidates = [
        {
            "artifact_path": "outputs/aged/log.txt",
            "artifact_kind": "intermediate_log",
            "proposed_classification": "candidate_archive",
        }
    ]
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(candidates), encoding="utf-8")
    res = _run(
        "scripts/generate_artifact_cleanup_candidates.py",
        "--candidates",
        str(path),
        expect_codes=(0,),
    )
    out = json.loads(res.stdout)
    assert out["artifact_type"] == "cleanup_candidate_report"


def test_generate_operator_runbook_no_inputs_returns_blocked():
    # No inputs => status = blocked => exit 3
    _run("scripts/generate_operator_runbook.py", expect_codes=(3,))
