from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.agent_golden_path import GoldenPathConfig, run_agent_golden_path
from spectrum_systems.modules.runtime.identity_enforcement import (
    RequiredIdentityError,
    ensure_required_ids,
    validate_required_ids,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_bundle_validation.py"


def test_missing_required_ids_fail_closed_at_runtime() -> None:
    with pytest.raises(RequiredIdentityError):
        validate_required_ids({"artifact_type": "eval_result"})


def test_ensure_required_ids_injects_deterministically() -> None:
    payload = {"artifact_type": "x"}
    first = ensure_required_ids(payload, run_id="run-det-001", trace_id="trace-det-001")
    second = ensure_required_ids(payload, run_id="run-det-001", trace_id="trace-det-001")
    assert first == second
    assert first["run_id"] == "run-det-001"
    assert first["trace_id"] == "trace-det-001"


def test_ensure_required_ids_does_not_mutate_input() -> None:
    payload = {"artifact_type": "x"}
    _ = ensure_required_ids(payload, run_id="run-immut-001", trace_id="trace-immut-001")
    assert "run_id" not in payload
    assert "trace_id" not in payload


def test_ids_propagate_across_replay_eval_certification_chain(tmp_path: Path) -> None:
    config = GoldenPathConfig(
        task_type="meeting_minutes",
        input_payload={"transcript": "identity chain test"},
        source_artifacts=[{"artifact_id": "src-001"}],
        context_config={},
        output_dir=tmp_path,
    )
    artifacts = run_agent_golden_path(config)
    run_id = artifacts["agent_execution_trace"]["agent_run_id"]
    trace_id = artifacts["agent_execution_trace"]["trace_id"]

    assert artifacts["eval_result"]["run_id"] == run_id
    assert artifacts["eval_result"]["trace_id"] == trace_id
    assert artifacts["replay_result"]["original_run_id"] == run_id
    assert artifacts["replay_result"]["replay_run_id"] == run_id
    assert artifacts["replay_result"]["trace_id"] == trace_id
    assert artifacts["done_certification_record"]["run_id"] == run_id
    assert artifacts["done_certification_record"]["trace_id"] == trace_id


def test_cli_artifact_includes_required_ids(tmp_path: Path) -> None:
    manifest = REPO_ROOT / "tests" / "fixtures" / "example_run_bundle_manifest.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(manifest),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["run_id"]
